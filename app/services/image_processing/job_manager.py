
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from pathlib import Path
from uuid import uuid4

from app.services.modules.context import ProcessingContext


class ImageProcessingJobManager:

    def __init__(self, max_workers=2):
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="image-processing",
        )
        self.jobs = {}
        self.lock = Lock()

    def submit(
        self,
        image_path,
        output_dir,
        processing_pipeline,
        module_ids,
        module_options=None,
        job_id=None,
    ):
        if processing_pipeline is None:
            raise ValueError("A processing pipeline is required.")

        if not isinstance(module_ids, (list, tuple)) or not module_ids:
            raise ValueError("At least one processing module is required.")

        if not isinstance(module_options, dict):
            raise TypeError("Module options must be a dictionary.")

        job_id = job_id or uuid4().hex
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        with self.lock:
            if job_id in self.jobs:
                raise ValueError(f"Job already exists: {job_id}")

            self.jobs[job_id] = {
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "message": "Image processing job queued.",
                "result": None,
                "error": None,
                "processing": None,
            }

        self.executor.submit(
            self._run_job,
            job_id,
            image_path,
            output_dir,
            processing_pipeline,
            list(module_ids),
            module_options,
        )

        return job_id

    def _run_job(
        self,
        job_id,
        image_path,
        output_dir,
        processing_pipeline,
        module_ids,
        module_options,
    ):
        context = ProcessingContext({
            "image_path": str(image_path),
            "output_dir": str(output_dir),
        })

        self._update_job(
            job_id,
            status="processing",
            progress=0,
            message="Preparing image processing job.",
        )

        try:
            def progress_callback(progress, message=None):
                progress = max(0, min(100, int(progress)))
                self._update_progress(job_id, progress, message)

            context = processing_pipeline.execute(
                module_ids=module_ids,
                context=context,
                module_options=module_options,
                progress_callback=progress_callback,
            )

            result = {
                "image_path": context.get("image_path"),
                "module_results": context.results,
            }

            if not result["image_path"]:
                raise RuntimeError(
                    "Processing pipeline did not produce an output image."
                )

            self._update_job(
                job_id,
                status="completed",
                progress=100,
                message="Image processing completed successfully.",
                result=result,
                processing={
                    "status": context.get_metadata("pipeline_status"),
                    "history": context.get_metadata("pipeline_history", []),
                },
            )

        except Exception as error:
            self._update_job(
                job_id,
                status="failed",
                message="Image processing failed.",
                error=str(error),
                processing={
                    "status": context.get_metadata(
                        "pipeline_status", "not_started"
                    ),
                    "history": context.get_metadata(
                        "pipeline_history", []
                    ),
                },
            )

    def _update_progress(self, job_id, progress, message=None):
        progress = max(0, min(99, int(progress)))

        updates = {"progress": progress}

        if message:
            updates["message"] = str(message)

        self._update_job(job_id, **updates)

    def _update_job(self, job_id, **updates):
        with self.lock:
            if job_id in self.jobs:
                self.jobs[job_id].update(updates)

    def get_job(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None


image_processing_jobs = ImageProcessingJobManager()
