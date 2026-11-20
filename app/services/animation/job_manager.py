
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from uuid import uuid4

from app.services.modules.context import ProcessingContext


class AnimationJobManager:

    def __init__(self, max_workers=1):
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="animation",
        )
        self.jobs = {}
        self.lock = Lock()

    def submit(
        self,
        engine,
        image_path,
        audio_path,
        output_dir,
        job_id=None,
        options=None,
        processing_pipeline=None,
        processing_module_ids=None,
        processing_module_options=None,
    ):
        job_id = job_id or uuid4().hex
        options = options or {}
        processing_module_ids = processing_module_ids or []
        processing_module_options = processing_module_options or {}

        with self.lock:
            self.jobs[job_id] = {
                "id": job_id,
                "status": "queued",
                "progress": 0,
                "message": "Animation job queued.",
                "result": None,
                "error": None,
                "processing": None,
            }

        self.executor.submit(
            self._run_job,
            job_id,
            engine,
            image_path,
            audio_path,
            output_dir,
            options,
            processing_pipeline,
            processing_module_ids,
            processing_module_options,
        )

        return job_id

    def _run_job(
        self,
        job_id,
        engine,
        image_path,
        audio_path,
        output_dir,
        options,
        processing_pipeline,
        processing_module_ids,
        processing_module_options,
    ):
        self._update_job(
            job_id,
            status="processing",
            progress=0,
            message="Preparing animation job.",
        )

        context = ProcessingContext({
            "image_path": image_path,
            "audio_path": audio_path,
            "output_dir": str(output_dir),
        })

        try:
            if processing_module_ids:
                if processing_pipeline is None:
                    raise RuntimeError(
                        "Processing modules were requested, "
                        "but no processing pipeline is configured."
                    )

                self._update_job(
                    job_id,
                    message="Running preprocessing modules.",
                )

                def preprocessing_progress(progress, message=None):
                    mapped_progress = int(
                        max(0, min(100, progress)) * 0.30
                    )
                    self._update_progress(
                        job_id,
                        mapped_progress,
                        message,
                    )

                context = processing_pipeline.execute(
                    module_ids=processing_module_ids,
                    context=context,
                    module_options=processing_module_options,
                    progress_callback=preprocessing_progress,
                )

                self._update_job(
                    job_id,
                    processing={
                        "status": context.get_metadata("pipeline_status"),
                        "history": context.get_metadata(
                            "pipeline_history", []
                        ),
                    },
                )

            processed_image = context.get("image_path")
            processed_audio = context.get("audio_path")

            if not processed_image or not processed_audio:
                raise RuntimeError(
                    "Processing pipeline did not provide valid "
                    "image and audio paths."
                )

            self._update_job(
                job_id,
                progress=30 if processing_module_ids else 0,
                message="Starting animation generation.",
            )

            def animation_progress(progress, message=None):
                progress = max(0, min(100, int(progress)))

                if processing_module_ids:
                    mapped_progress = 30 + int(progress * 0.70)
                else:
                    mapped_progress = progress

                self._update_progress(
                    job_id,
                    mapped_progress,
                    message,
                )

            result = engine.generate(
                image_path=processed_image,
                audio_path=processed_audio,
                output_dir=output_dir,
                options=options,
                progress_callback=animation_progress,
            )

            self._update_job(
                job_id,
                status="completed",
                progress=100,
                message="Animation generated successfully.",
                result=result,
            )

        except Exception as error:
            processing_info = {
                "status": context.get_metadata(
                    "pipeline_status", "not_started"
                ),
                "history": context.get_metadata("pipeline_history", []),
            }

            self._update_job(
                job_id,
                status="failed",
                message="Animation generation failed.",
                error=str(error),
                processing=processing_info,
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


animation_jobs = AnimationJobManager()
