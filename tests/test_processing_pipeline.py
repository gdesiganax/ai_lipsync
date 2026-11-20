
import unittest

from app.services.modules.base import ProcessingModule
from app.services.modules.registry import ModuleRegistry
from app.services.modules.context import ProcessingContext
from app.services.modules.pipeline import ProcessingPipeline


class FakeFaceModule(ProcessingModule):

    module_id = "face_enhancement"
    name = "Face Enhancement"
    description = "Test face enhancement module."

    def __init__(self, config=None):
        self.config = config or {}

    def is_available(self):
        return True

    def process(self, input_data, options=None, progress_callback=None):
        input_data.set("image_path", "enhanced_image.jpg")
        return {"image": "enhanced_image.jpg"}


class FakeAudioModule(ProcessingModule):

    module_id = "audio_cleanup"
    name = "Audio Cleanup"
    description = "Test audio cleanup module."

    def __init__(self, config=None):
        self.config = config or {}

    def is_available(self):
        return True

    def process(self, input_data, options=None, progress_callback=None):
        image = input_data.get("image_path")

        return {
            "image_received": image,
            "audio": "cleaned_audio.wav"
        }


class UnavailableModule(FakeFaceModule):

    module_id = "unavailable_module"

    def is_available(self):
        return False


class FailingModule(FakeFaceModule):

    module_id = "failing_module"

    def process(self, input_data, options=None, progress_callback=None):
        raise RuntimeError("Simulated processing failure.")


class ProcessingPipelineTests(unittest.TestCase):

    def setUp(self):
        self.registry = ModuleRegistry()
        self.pipeline = ProcessingPipeline(self.registry)

    def test_modules_execute_in_sequence(self):
        self.registry.register(FakeFaceModule())
        self.registry.register(FakeAudioModule())

        context = ProcessingContext({
            "image_path": "original_image.jpg",
            "audio_path": "original_audio.wav"
        })

        result = self.pipeline.execute(
            ["face_enhancement", "audio_cleanup"],
            context
        )

        self.assertEqual(
            result.get("image_path"),
            "enhanced_image.jpg"
        )

        self.assertEqual(
            result.get_result("face_enhancement"),
            {"image": "enhanced_image.jpg"}
        )

        self.assertEqual(
            result.get_result("audio_cleanup")["image_received"],
            "enhanced_image.jpg"
        )

    def test_missing_module_raises_error(self):
        with self.assertRaisesRegex(
            ValueError,
            "Processing module not found"
        ):
            self.pipeline.execute(
                ["unknown_module"],
                ProcessingContext()
            )

    def test_unavailable_module_raises_error(self):
        self.registry.register(UnavailableModule())

        with self.assertRaisesRegex(
            RuntimeError,
            "Processing module is unavailable"
        ):
            self.pipeline.execute(
                ["unavailable_module"],
                ProcessingContext()
            )

    def test_processing_failure_is_propagated(self):
        self.registry.register(FailingModule())

        with self.assertRaisesRegex(
            RuntimeError,
            "Simulated processing failure"
        ):
            self.pipeline.execute(
                ["failing_module"],
                ProcessingContext()
            )

    def test_empty_pipeline_raises_error(self):
        with self.assertRaisesRegex(
            ValueError,
            "at least one module"
        ):
            self.pipeline.execute(
                [],
                ProcessingContext()
            )

    def test_progress_callback(self):
        self.registry.register(FakeFaceModule())
        self.registry.register(FakeAudioModule())

        progress_updates = []

        self.pipeline.execute(
            ["face_enhancement", "audio_cleanup"],
            ProcessingContext(),
            progress_callback=lambda progress, message: (
                progress_updates.append((progress, message))
            )
        )

        self.assertEqual(progress_updates[0][0], 0)
        self.assertEqual(progress_updates[-1][0], 100)
        self.assertEqual(len(progress_updates), 3)

    
    def test_pipeline_execution_history(self):
        self.registry.register(FakeFaceModule())
        self.registry.register(FakeAudioModule())

        result = self.pipeline.execute(
            ["face_enhancement", "audio_cleanup"],
            ProcessingContext()
        )

        history = result.get_metadata("pipeline_history")

        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["status"], "completed")
        self.assertEqual(history[1]["status"], "completed")
        self.assertEqual(
            result.get_metadata("pipeline_status"),
            "completed"
        )

    def test_stop_after_module(self):
        self.registry.register(FakeFaceModule())
        self.registry.register(FakeAudioModule())

        result = self.pipeline.execute(
            ["face_enhancement", "audio_cleanup"],
            ProcessingContext(),
            stop_after="face_enhancement"
        )

        self.assertEqual(
            result.get_metadata("pipeline_status"),
            "stopped"
        )

        self.assertEqual(
            len(result.get_metadata("pipeline_history")),
            1
        )

        self.assertIsNone(
            result.get_result("audio_cleanup")
        )

    def test_pipeline_records_processing_failure(self):
        self.registry.register(FailingModule())

        context = ProcessingContext()

        with self.assertRaisesRegex(
            RuntimeError,
            "Simulated processing failure"
        ):
            self.pipeline.execute(
                ["failing_module"],
                context
            )

        self.assertEqual(
            context.get_metadata("pipeline_status"),
            "failed"
        )

        history = context.get_metadata("pipeline_history")

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "failed")
        self.assertIn("error", history[0])



if __name__ == "__main__":
    unittest.main()
