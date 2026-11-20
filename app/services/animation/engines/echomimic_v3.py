
import logging
import mimetypes
import time
import uuid

from pathlib import Path

import requests

from app.services.animation.base import AnimationEngine


logger = logging.getLogger(__name__)


class EchoMimicV3Engine(AnimationEngine):

    engine_id = "echomimic_v3"
    name = "EchoMimic V3"
    version = "3.1"
    task_type = "image_to_video"

    capabilities = [
        "audio_driven_animation",
        "facial_expression",
        "head_movement",
        "upper_body_animation",
    ]

    # GPU inference happens on the remote worker, not Flask's machine.
    requirements = {
        "gpu": False,
        "remote_gpu": True,
    }

    description = (
        "Audio-driven human animation with facial expressions "
        "and upper-body movement, powered by a remote EchoMimic V3 "
        "Preview inference worker."
    )

    options = [
        {
            "name": "prompt",
            "label": "Animation prompt",
            "type": "text",
            "default": "A person speaking naturally.",
        },
        {
            "name": "seed",
            "label": "Random seed",
            "type": "number",
            "default": 43,
        },
        {
            "name": "num_inference_steps",
            "label": "Inference steps",
            "type": "number",
            "default": 25,
            "min": 1,
            "max": 100,
        },
    ]

    
    def __init__(self, config):

        worker_url = config.get("ECHOMIMIC_WORKER_URL")
        worker_token = config.get("ECHOMIMIC_WORKER_TOKEN")

        self.worker_url = (
            str(worker_url).strip().rstrip("/")
            if worker_url else ""
        )

        self.api_token = (
            str(worker_token).strip()
            if worker_token else ""
        )

        self.timeout = int(
            config.get("ECHOMIMIC_WORKER_TIMEOUT") or 14400
        )

        self.poll_interval = float(
            config.get("ECHOMIMIC_WORKER_POLL_INTERVAL") or 3
        )

        self.connect_timeout = int(
            config.get("ECHOMIMIC_WORKER_CONNECT_TIMEOUT") or 30
        )

        self.upload_timeout = int(
            config.get("ECHOMIMIC_WORKER_UPLOAD_TIMEOUT") or 300
        )


    # -----------------------------------------------------
    # Availability
    # -----------------------------------------------------

    def is_available(self):

        # Do not make network requests during Flask startup.
        # This only checks whether the remote worker is configured.
        return bool(
            self.worker_url
            and self.api_token
        )

    # -----------------------------------------------------
    # Helpers
    # -----------------------------------------------------

    def get_headers(self):

        return {
            "Authorization": f"Bearer {self.api_token}",
        }

    @staticmethod
    def get_content_type(file_path):

        content_type, _ = mimetypes.guess_type(
            str(file_path)
        )

        return content_type or "application/octet-stream"

    @staticmethod
    def raise_for_worker_error(response, action):

        try:
            response.raise_for_status()

        except requests.RequestException as exc:

            detail = ""

            try:
                detail = response.json().get("detail", "")
            except (ValueError, AttributeError):
                detail = response.text[:500]

            raise RuntimeError(
                f"EchoMimic worker failed while {action}. "
                f"HTTP {response.status_code}: {detail}"
            ) from exc

    # -----------------------------------------------------
    # Submit job
    # -----------------------------------------------------

    def submit_job(
        self,
        image_path,
        audio_path,
        options,
    ):

        image_path = Path(image_path)
        audio_path = Path(audio_path)

        if not image_path.is_file():
            raise FileNotFoundError(
                f"Portrait image not found: {image_path}"
            )

        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        url = f"{self.worker_url}/jobs"

        data = {
            "prompt": str(
                options.get(
                    "prompt",
                    "A person speaking naturally.",
                )
            ),
            "seed": int(options.get("seed", 43)),
            "steps": int(
                options.get("num_inference_steps", 25)
            ),
        }

        if not 1 <= data["steps"] <= 100:
            raise ValueError(
                "Inference steps must be between 1 and 100."
            )

        with image_path.open("rb") as image_file, \
                audio_path.open("rb") as audio_file:

            files = {
                "image": (
                    image_path.name,
                    image_file,
                    self.get_content_type(image_path),
                ),
                "audio": (
                    audio_path.name,
                    audio_file,
                    self.get_content_type(audio_path),
                ),
            }

            response = requests.post(
                url,
                headers=self.get_headers(),
                data=data,
                files=files,
                timeout=(
                    self.connect_timeout,
                    self.upload_timeout,
                ),
            )

        self.raise_for_worker_error(
            response,
            "submitting the generation job",
        )

        result = response.json()

        job_id = result.get("job_id")

        if not job_id:
            raise RuntimeError(
                "EchoMimic worker did not return a job ID."
            )

        logger.info(
            "Submitted EchoMimic job %s.",
            job_id,
        )

        return job_id

    # -----------------------------------------------------
    # Poll job progress
    # -----------------------------------------------------

    def wait_for_job(
        self,
        job_id,
        progress_callback=None,
    ):

        url = (
            f"{self.worker_url}/jobs/{job_id}"
        )

        started_at = time.monotonic()

        while True:

            elapsed = time.monotonic() - started_at

            if elapsed >= self.timeout:
                raise TimeoutError(
                    "EchoMimic generation exceeded the "
                    f"{self.timeout}-second timeout."
                )

            response = requests.get(
                url,
                headers=self.get_headers(),
                timeout=(
                    self.connect_timeout,
                    60,
                ),
            )

            self.raise_for_worker_error(
                response,
                "checking job progress",
            )

            job = response.json()

            status = job.get("status")
            progress = int(
                job.get("progress", 0)
            )

            message = job.get(
                "message",
                "Generating video.",
            )

            if progress_callback:

                progress_callback(
                    progress,
                    message,
                )

            if status == "completed":

                logger.info(
                    "EchoMimic job %s completed.",
                    job_id,
                )

                return job

            if status == "failed":

                raise RuntimeError(
                    "EchoMimic generation failed: "
                    f"{message}"
                )

            if status not in ("queued", "processing"):

                raise RuntimeError(
                    "Worker returned an unknown job status: "
                    f"{status}"
                )

            time.sleep(
                min(
                    self.poll_interval,
                    max(0, self.timeout - elapsed),
                )
            )

    # -----------------------------------------------------
    # Download result
    # -----------------------------------------------------

    def download_result(
        self,
        job_id,
        output_dir,
    ):

        output_dir = Path(output_dir)

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = (
            f"echomimic_{uuid.uuid4().hex}.mp4"
        )

        output_path = output_dir / filename
        temporary_path = output_dir / f"{filename}.part"

        url = (
            f"{self.worker_url}/jobs/{job_id}/result"
        )

        try:

            with requests.get(
                url,
                headers=self.get_headers(),
                stream=True,
                timeout=(
                    self.connect_timeout,
                    300,
                ),
            ) as response:

                self.raise_for_worker_error(
                    response,
                    "downloading the generated video",
                )

                with temporary_path.open("wb") as output:

                    for chunk in response.iter_content(
                        chunk_size=1024 * 1024
                    ):

                        if chunk:
                            output.write(chunk)

            if not temporary_path.is_file():
                raise RuntimeError(
                    "The downloaded video file is missing."
                )

            if temporary_path.stat().st_size == 0:
                raise RuntimeError(
                    "The downloaded video file is empty."
                )

            temporary_path.replace(output_path)

            logger.info(
                "Downloaded EchoMimic result: %s",
                output_path,
            )

            return output_path

        except Exception:

            temporary_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

            raise

    # -----------------------------------------------------
    # Generate
    # -----------------------------------------------------

    def generate(
        self,
        image_path,
        audio_path,
        output_dir,
        options=None,
        progress_callback=None,
    ):

        if not self.is_available():
            raise RuntimeError(
                "EchoMimic remote worker is not configured. "
                "Set ECHOMIMIC_WORKER_URL and "
                "ECHOMIMIC_WORKER_TOKEN."
            )

        options = options or {}

        self.report_progress(
            progress_callback,
            5,
            "Connecting to EchoMimic worker.",
        )

        job_id = self.submit_job(
            image_path=image_path,
            audio_path=audio_path,
            options=options,
        )

        self.report_progress(
            progress_callback,
            10,
            "Job submitted. Waiting for video generation.",
        )

        self.wait_for_job(
            job_id=job_id,
            progress_callback=progress_callback,
        )

        self.report_progress(
            progress_callback,
            95,
            "Downloading generated video.",
        )

        output_path = self.download_result(
            job_id=job_id,
            output_dir=output_dir,
        )

        self.report_progress(
            progress_callback,
            100,
            "EchoMimic video generation completed.",
        )

        return output_path

    # -----------------------------------------------------
    # Progress reporting
    # -----------------------------------------------------

    @staticmethod
    def report_progress(
        callback,
        progress,
        message,
    ):

        if callback:
            callback(progress, message)
