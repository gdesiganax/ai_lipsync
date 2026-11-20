
import time
import unittest

from app.services.animation.job_manager import AnimationJobManager
from app.services.modules.base import ProcessingModule
from app.services.modules.pipeline import ProcessingPipeline
from app.services.modules.registry import ModuleRegistry


class FakeImageProcessor(ProcessingModule):

    module_id = "image_processor"
    name = "Fake Image Processor"

    def is_available(self):
        return True

    def process(self, input_data, options=None, progress_callback=None):
        input_data.set("image_path", "processed-image.png")

        return {
            "image_path": "processed-image.png",
        }


class FailingProcessor(ProcessingModule):

    module_id = "failing_processor"
    name = "Failing Processor"

    def is_available(self):
        return True

    def process(self, input_data, options=None, progress_callback=None):
        raise RuntimeError("Preprocessing failed.")


class FakeAnimationEngine:

    def __init__(self):
        self.received_image = None
        self.received_audio = None
        self.called = False

    def generate(
        self,
        image_path,
        audio_path,
        output_dir,
        options=None,
        progress_callback=None,
    ):
        self.called = True
        self.received_image = image_path
        self.received_audio = audio_path

        if progress_callback:
            progress_callback(50, "Rendering animation.")

        return {"video_path": "test-video.mp4"}


class AnimationPipelineIntegrationTests(unittest.TestCase):

    def setUp(self):
        self.manager = AnimationJobManager(max_workers=1)

        self.registry = ModuleRegistry()
        self.pipeline = ProcessingPipeline(self.registry)

        self.engine = FakeAnimationEngine()

    def tearDown(self):
        self.manager.executor.shutdown(wait=True)

    def wait_for_job(self, job_id):
        for _ in range(100):
            job = self.manager.get_job(job_id)

            if job["status"] in ("completed", "failed"):
                return job

            time.sleep(0.05)

        self.fail("Animation job did not finish in time.")

    def test_animation_works_without_preprocessing(self):
        job_id = self.manager.submit(
            engine=self.engine,
            image_path="original-image.png",
            audio_path="original-audio.wav",
            output_dir="test-output",
        )

        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "completed")
        self.assertTrue(self.engine.called)
        self.assertEqual(
            self.engine.received_image,
            "original-image.png",
        )
        self.assertEqual(
            self.engine.received_audio,
            "original-audio.wav",
        )

    def test_preprocessing_runs_before_animation(self):
        self.registry.register(FakeImageProcessor())

        job_id = self.manager.submit(
            engine=self.engine,
            image_path="original-image.png",
            audio_path="original-audio.wav",
            output_dir="test-output",
            processing_pipeline=self.pipeline,
            processing_module_ids=["image_processor"],
        )

        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "completed")
        self.assertTrue(self.engine.called)

        self.assertEqual(
            self.engine.received_image,
            "processed-image.png",
        )
        self.assertEqual(
            self.engine.received_audio,
            "original-audio.wav",
        )

        self.assertEqual(
            job["processing"]["status"],
            "completed",
        )

    def test_preprocessing_failure_prevents_animation(self):
        self.registry.register(FailingProcessor())

        job_id = self.manager.submit(
            engine=self.engine,
            image_path="original-image.png",
            audio_path="original-audio.wav",
            output_dir="test-output",
            processing_pipeline=self.pipeline,
            processing_module_ids=["failing_processor"],
        )

        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "failed")
        self.assertFalse(self.engine.called)
        self.assertIn("Preprocessing failed", job["error"])

        self.assertEqual(
            job["processing"]["status"],
            "failed",
        )


if __name__ == "__main__":
    unittest.main()
