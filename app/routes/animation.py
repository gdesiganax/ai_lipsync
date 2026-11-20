
import json
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)
from werkzeug.utils import secure_filename

from app.services.animation.job_manager import animation_jobs
from app.services.animation.loader import load_engines


animation_bp = Blueprint(
    "animation",
    __name__,
    url_prefix="/animation",
)


def get_engine_registry():
    if "animation_engine_registry" not in current_app.extensions:
        current_app.extensions["animation_engine_registry"] = (
            load_engines(current_app.config)
        )

    return current_app.extensions["animation_engine_registry"]


def allowed_file(filename, extensions):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in extensions
    )


@animation_bp.route("/")
def index():
    return render_template("animation/index.html")


@animation_bp.route("/api/engines", methods=["GET"])
def engines():
    registry = get_engine_registry()

    return jsonify({
        "success": True,
        "engines": registry.get_all(),
    })


@animation_bp.route("/api/generate", methods=["POST"])
def generate():
    registry = get_engine_registry()

    engine_id = request.form.get("engine", "").strip()
    image = request.files.get("image")
    audio = request.files.get("audio")

    if not engine_id:
        return jsonify({
            "success": False,
            "message": "Please select an animation engine.",
        }), 400

    engine = registry.get(engine_id)

    if engine is None:
        return jsonify({
            "success": False,
            "message": "Invalid animation engine.",
        }), 400

    if image is None or not image.filename:
        return jsonify({
            "success": False,
            "message": "Please upload a source image.",
        }), 400

    if audio is None or not audio.filename:
        return jsonify({
            "success": False,
            "message": "Please upload an audio file.",
        }), 400

    if not allowed_file(
        image.filename,
        {"png", "jpg", "jpeg", "webp"},
    ):
        return jsonify({
            "success": False,
            "message": "Unsupported image format.",
        }), 400

    if not allowed_file(
        audio.filename,
        {"wav", "mp3", "m4a", "aac", "ogg", "flac"},
    ):
        return jsonify({
            "success": False,
            "message": "Unsupported audio format.",
        }), 400

    if not engine.is_available():
        return jsonify({
            "success": False,
            "message": (
                f"{engine.name} is not installed yet. "
                "Please install its model files and dependencies."
            ),
        }), 503

    # Parse engine-specific generation options.
    try:
        options = json.loads(request.form.get("options", "{}"))

        if not isinstance(options, dict):
            return jsonify({
                "success": False,
                "message": "Generation options must be a JSON object.",
            }), 400

    except (json.JSONDecodeError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid generation options.",
        }), 400

    job_id = uuid4().hex

    upload_dir = (
        Path(current_app.config["UPLOAD_FOLDER"])
        / "animation"
        / job_id
    )

    output_dir = (
        Path(current_app.config["OUTPUT_FOLDER"])
        / "animation"
        / job_id
    )

    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_path = upload_dir / secure_filename(image.filename)
    audio_path = upload_dir / secure_filename(audio.filename)

    try:
        image.save(image_path)
        audio.save(audio_path)

        animation_jobs.submit(
            engine=engine,
            image_path=image_path,
            audio_path=audio_path,
            output_dir=output_dir,
            job_id=job_id,
            options=options,
            processing_pipeline=current_app.extensions["processing_pipeline"],
        )

        return jsonify({
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "message": "Animation job submitted successfully.",
        }), 202

    except Exception:
        current_app.logger.exception(
            "Failed to submit animation job: %s",
            job_id,
        )

        return jsonify({
            "success": False,
            "message": "Unable to submit animation job.",
        }), 500


@animation_bp.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    job = animation_jobs.get_job(job_id)

    if job is None:
        return jsonify({
            "success": False,
            "message": "Animation job not found.",
        }), 404

    return jsonify({
        "success": True,
        "job": job,
    })


@animation_bp.route("/api/jobs/<job_id>/video", methods=["GET"])
def get_job_video(job_id):
    job = animation_jobs.get_job(job_id)

    if job is None:
        return jsonify({
            "success": False,
            "message": "Animation job not found.",
        }), 404

    if job["status"] != "completed":
        return jsonify({
            "success": False,
            "message": "Animation is not completed yet.",
        }), 409

    result = job.get("result") or {}
    video_path = result.get("video_path")

    if not video_path:
        return jsonify({
            "success": False,
            "message": "Video file is not available.",
        }), 404

    output_root = Path(
        current_app.config["OUTPUT_FOLDER"]
    ).resolve()

    video_path = Path(video_path).resolve()

    try:
        video_path.relative_to(output_root)
    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid video file location.",
        }), 403

    if not video_path.is_file():
        return jsonify({
            "success": False,
            "message": "Generated video file not found.",
        }), 404

    return send_file(
        video_path,
        mimetype="video/mp4",
        as_attachment=False,
        download_name="animation.mp4",
    )
