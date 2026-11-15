import subprocess
import sys
import threading
import logging
from pathlib import Path

from flask import current_app


jobs = {}
jobs_lock = threading.Lock()


def update_job(job_id, **updates):
    with jobs_lock:
        jobs.setdefault(job_id, {}).update(updates)


def get_job(job_id):
    with jobs_lock:
        return jobs.get(job_id)


def run_generation(app, job_id, image_path, audio_path, output_dir):
    with app.app_context():
        config = app.config

        log_path = config["LOG_FOLDER"] / f"{job_id}.log"

        update_job(
            job_id,
            status="running",
            message="SadTalker is processing your files."
        )

        command = [
            sys.executable,
            "inference.py",
            "--driven_audio", str(image_or_audio_path(audio_path)),
            "--source_image", str(image_or_audio_path(image_path)),
            "--result_dir", str(output_dir),
            "--checkpoint_dir", str(config["SADTALKER_CHECKPOINTS"]),
            "--size", str(config["VIDEO_SIZE"]),
            "--preprocess", config["VIDEO_PREPROCESS"],
            "--cpu"
        ]

        try:
            app.logger.info("Starting SadTalker job: %s", job_id)

            with open(log_path, "w", encoding="utf-8") as log_file:
                log_file.write(f"Starting job: {job_id}\n")
                log_file.flush()

                result = subprocess.run(
                    command,
                    cwd=config["SADTALKER_DIR"],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=config["GENERATION_TIMEOUT"]
                )

            if result.returncode != 0:
                update_job(
                    job_id,
                    status="failed",
                    message="SadTalker encountered an error.",
                    log=str(log_path)
                )
                app.logger.error("SadTalker failed: %s", job_id)
                return

            videos = list(Path(output_dir).rglob("*.mp4"))

            if not videos:
                update_job(
                    job_id,
                    status="failed",
                    message="No MP4 video was produced.",
                    log=str(log_path)
                )
                return

            update_job(
                job_id,
                status="completed",
                message="Video generation completed.",
                video=str(videos[0]),
                log=str(log_path)
            )

            app.logger.info("SadTalker completed job: %s", job_id)

        except subprocess.TimeoutExpired:
            update_job(
                job_id,
                status="failed",
                message="Video generation timed out.",
                log=str(log_path)
            )
            app.logger.exception("SadTalker timeout: %s", job_id)

        except Exception:
            update_job(
                job_id,
                status="failed",
                message="An unexpected generation error occurred.",
                log=str(log_path)
            )
            app.logger.exception("SadTalker error: %s", job_id)


def image_or_audio_path(path):
    return str(Path(path).resolve())


def start_generation(app, job_id, image_path, audio_path, output_dir):
    update_job(
        job_id,
        status="queued",
        message="Your video is waiting to be processed."
    )

    thread = threading.Thread(
        target=run_generation,
        args=(app, job_id, image_path, audio_path, output_dir),
        daemon=True
    )
    thread.start()