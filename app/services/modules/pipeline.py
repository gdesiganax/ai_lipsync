
from datetime import datetime, timezone

from app.services.modules.context import ProcessingContext


class ProcessingPipeline:

    def __init__(self, registry):
        self.registry = registry

    def execute(
        self,
        module_ids,
        context,
        module_options=None,
        progress_callback=None,
        stop_after=None,
    ):
        if not isinstance(context, ProcessingContext):
            context = ProcessingContext(context)

        if not isinstance(module_ids, (list, tuple)):
            raise TypeError("module_ids must be a list or tuple.")

        if not module_ids:
            raise ValueError("Pipeline requires at least one module.")

        if any(
            not isinstance(module_id, str) or not module_id.strip()
            for module_id in module_ids
        ):
            raise ValueError("Every module ID must be a non-empty string.")

        if len(set(module_ids)) != len(module_ids):
            raise ValueError("Duplicate module IDs are not allowed.")

        if stop_after is not None and stop_after not in module_ids:
            raise ValueError("stop_after must reference a pipeline module.")

        if module_options is None:
            module_options = {}

        if not isinstance(module_options, dict):
            raise TypeError("module_options must be a dictionary.")

        history = []
        total = len(module_ids)

        context.set_metadata("pipeline_status", "processing")
        context.set_metadata("pipeline_started_at", self._timestamp())

        try:
            for index, module_id in enumerate(module_ids):
                started_at = self._timestamp()

                context.set_metadata("current_module", module_id)

                try:
                    module = self.registry.get(module_id)

                    if module is None:
                        raise ValueError(
                            f"Processing module not found: {module_id}"
                        )

                    if not module.is_available():
                        raise RuntimeError(
                            f"Processing module is unavailable: {module_id}"
                        )

                    options = module_options.get(module_id, {})

                    if not isinstance(options, dict):
                        raise TypeError(
                            f"Options for {module_id} must be a dictionary."
                        )

                    if progress_callback:
                        progress_callback(
                            int((index / total) * 100),
                            f"Running {module.name}",
                        )

                    result = module.process(
                        input_data=context,
                        options=options,
                        progress_callback=progress_callback,
                    )

                    context.add_result(module_id, result)

                    history.append({
                        "module_id": module_id,
                        "status": "completed",
                        "started_at": started_at,
                        "completed_at": self._timestamp(),
                    })

                except Exception as error:
                    history.append({
                        "module_id": module_id,
                        "status": "failed",
                        "started_at": started_at,
                        "failed_at": self._timestamp(),
                        "error": str(error),
                    })
                    raise

                if stop_after == module_id:
                    context.set_metadata("pipeline_status", "stopped")

                    if progress_callback:
                        progress_callback(
                            int(((index + 1) / total) * 100),
                            "Processing pipeline stopped.",
                        )

                    break

            else:
                context.set_metadata("pipeline_status", "completed")

                if progress_callback:
                    progress_callback(
                        100,
                        "Processing pipeline completed.",
                    )

        except Exception as error:
            context.set_metadata("pipeline_status", "failed")
            context.set_metadata("pipeline_error", str(error))
            raise

        finally:
            context.set_metadata("pipeline_history", history)
            context.set_metadata("pipeline_finished_at", self._timestamp())
            context.set_metadata("current_module", None)

        return context

    @staticmethod
    def _timestamp():
        return datetime.now(timezone.utc).isoformat()
