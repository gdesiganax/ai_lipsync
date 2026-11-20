
import json
import mimetypes
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

from app.services.image_processing import image_processing_jobs


image_studio_bp = Blueprint(
    "image_studio",
    __name__,
    url_prefix="/image-studio",
)

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}


def get_module_registry():
    return current_app.extensions["processing_module_registry"]


def allowed_image(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_IMAGE_EXTENSIONS
    )


def resolve_job_image(job, job_id):
    """Return a validated output image path for this job."""
    result = job.get("result") or {}
    image_path = result.get("image_path")

    if not image_path:
        return None, (jsonify({
            "success": False,
            "message": "Processed image is not available.",
        }), 404)

    output_root = (
        Path(current_app.config["OUTPUT_FOLDER"])
        / "image_processing"
        / job_id
    ).resolve()

    image_path = Path(image_path).resolve()

    try:
        image_path.relative_to(output_root)
    except ValueError:
        return None, (jsonify({
            "success": False,
            "message": "Invalid image file location.",
        }), 403)

    if not image_path.is_file():
        return None, (jsonify({
            "success": False,
            "message": "Processed image file not found.",
        }), 404)

    return image_path, None


@image_studio_bp.route("/")
def index():
    return render_template("image_studio/index.html")


@image_studio_bp.route("/api/modules", methods=["GET"])
def modules():
    registry = get_module_registry()

    return jsonify({
        "success": True,
        "modules": registry.get_all(),
    })


@image_studio_bp.route("/api/process", methods=["POST"])
def process_image():
    registry = get_module_registry()

    image = request.files.get("image")

    if image is None or not image.filename:
        return jsonify({
            "success": False,
            "message": "Please upload an image.",
        }), 400

    if not allowed_image(image.filename):
        return jsonify({
            "success": False,
            "message": "Unsupported image format. Use PNG, JPG or WEBP.",
        }), 400

    try:
        module_ids = json.loads(request.form.get("module_ids", "[]"))
        module_options = json.loads(
            request.form.get("module_options", "{}")
        )

        if (
            not isinstance(module_ids, list)
            or not module_ids
            or any(
                not isinstance(module_id, str) or not module_id.strip()
                for module_id in module_ids
            )
        ):
            raise ValueError("Select at least one valid processing module.")

        if len(set(module_ids)) != len(module_ids):
            raise ValueError("Duplicate processing modules are not allowed.")

        if not isinstance(module_options, dict):
            raise ValueError("Module options must be a JSON object.")

    except (json.JSONDecodeError, TypeError, ValueError) as error:
        return jsonify({
            "success": False,
            "message": str(error) or "Invalid processing options.",
        }), 400

    for module_id in module_ids:
        module = registry.get(module_id)

        if module is None:
            return jsonify({
                "success": False,
                "message": f"Unknown processing module: {module_id}",
            }), 400

        if not module.is_available():
            return jsonify({
                "success": False,
                "message": f"{module.name} is currently unavailable.",
            }), 503

    job_id = uuid4().hex

    upload_dir = (
        Path(current_app.config["UPLOAD_FOLDER"])
        / "image_processing"
        / job_id
    )

    output_dir = (
        Path(current_app.config["OUTPUT_FOLDER"])
        / "image_processing"
        / job_id
    )

    upload_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = secure_filename(image.filename)

    if not filename:
        return jsonify({
            "success": False,
            "message": "Invalid image filename.",
        }), 400

    image_path = upload_dir / filename

    try:
        image.save(image_path)

        image_processing_jobs.submit(
            image_path=image_path,
            output_dir=output_dir,
            processing_pipeline=current_app.extensions[
                "processing_pipeline"
            ],
            module_ids=module_ids,
            module_options=module_options,
            job_id=job_id,
        )

        return jsonify({
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "message": "Image processing job submitted successfully.",
        }), 202

    except Exception:
        current_app.logger.exception(
            "Failed to submit image processing job: %s",
            job_id,
        )

        return jsonify({
            "success": False,
            "message": "Unable to submit image processing job.",
        }), 500


@image_studio_bp.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id):
    job = image_processing_jobs.get_job(job_id)

    if job is None:
        return jsonify({
            "success": False,
            "message": "Image processing job not found.",
        }), 404

    return jsonify({
        "success": True,
        "job": job,
    })


@image_studio_bp.route(
    "/api/jobs/<job_id>/preview",
    methods=["GET"],
)
def preview_image(job_id):
    job = image_processing_jobs.get_job(job_id)

    if job is None:
        return jsonify({
            "success": False,
            "message": "Image processing job not found.",
        }), 404

    if job["status"] != "completed":
        return jsonify({
            "success": False,
            "message": "Image processing is not completed yet.",
        }), 409

    image_path, error_response = resolve_job_image(job, job_id)

    if error_response:
        return error_response

    mimetype = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"

    return send_file(
        image_path,
        mimetype=mimetype,
        as_attachment=False,
    )


@image_studio_bp.route(
    "/api/jobs/<job_id>/download",
    methods=["GET"],
)
def download_image(job_id):
    job = image_processing_jobs.get_job(job_id)

    if job is None:
        return jsonify({
            "success": False,
            "message": "Image processing job not found.",
        }), 404

    if job["status"] != "completed":
        return jsonify({
            "success": False,
            "message": "Image processing is not completed yet.",
        }), 409

    image_path, error_response = resolve_job_image(job, job_id)

    if error_response:
        return error_response

    return send_file(
        image_path,
        mimetype=mimetypes.guess_type(image_path.name)[0]
        or "application/octet-stream",
        as_attachment=True,
        download_name=image_path.name,
    )
