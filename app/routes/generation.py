import uuid
from pathlib import Path

from flask import (
    Blueprint,
    jsonify,
    request,
    current_app,
    send_file
)
from werkzeug.utils import secure_filename

from app.services.sadtalker import start_generation, get_job


generation_bp = Blueprint("generation", __name__, url_prefix="/api")

ALLOWED_IMAGES = {".jpg", ".jpeg", ".png"}
ALLOWED_AUDIO = {".wav", ".mp3", ".m4a"}


@generation_bp.route("/generate", methods=["POST"])
def generate():
    image = request.files.get("image")
    audio = request.files.get("audio")

    if not image or not audio:
        return jsonify({
            "success": False,
            "message": "Please upload both an image and audio file."
        }), 400

    image_ext = Path(secure_filename(image.filename)).suffix.lower()
    audio_ext = Path(secure_filename(audio.filename)).suffix.lower()

    if image_ext not in ALLOWED_IMAGES:
        return jsonify({
            "success": False,
            "message": "Unsupported image format."
        }), 400

    if audio_ext not in ALLOWED_AUDIO:
        return jsonify({
            "success": False,
            "message": "Unsupported audio format."
        }), 400

    job_id = uuid.uuid4().hex

    upload_dir = current_app.config["UPLOAD_FOLDER"] / job_id
    output_dir = current_app.config["OUTPUT_FOLDER"] / job_id

    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_path = upload_dir / f"source{image_ext}"
    audio_path = upload_dir / f"audio{audio_ext}"

    image.save(image_path)
    audio.save(audio_path)

    app = current_app._get_current_object()

    start_generation(
        app,
        job_id,
        image_path,
        audio_path,
        output_dir
    )

    return jsonify({
        "success": True,
        "job_id": job_id,
        "status": "queued",
        "message": "Your video generation request has been received."
    }), 202


@generation_bp.route("/status/<job_id>", methods=["GET"])
def generation_status(job_id):
    job = get_job(job_id)

    if not job:
        return jsonify({
            "success": False,
            "message": "Generation job not found."
        }), 404

    response = {
        "success": True,
        "job_id": job_id,
        "status": job["status"],
        "message": job["message"]
    }

    if job["status"] == "completed":
        response["video_url"] = f"/api/video/{job_id}"

    return jsonify(response)


@generation_bp.route("/video/<job_id>", methods=["GET"])
def download_video(job_id):
    job = get_job(job_id)

    if not job or job["status"] != "completed":
        return jsonify({
            "success": False,
            "message": "Video is not available."
        }), 404

    video_path = Path(job["video"])

    if not video_path.is_file():
        return jsonify({
            "success": False,
            "message": "Video file not found."
        }), 404

    return send_file(
        video_path,
        mimetype="video/mp4",
        as_attachment=False,
        download_name="talking-video.mp4"
    )