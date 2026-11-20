
import io
import json
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image

from app import create_app
from config import Config


class TestConfig(Config):
    TESTING = True


class ImageStudioAPITests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp_dir.name)

        class TemporaryConfig(TestConfig):
            UPLOAD_FOLDER = cls.root / "uploads"
            OUTPUT_FOLDER = cls.root / "outputs"
            LOG_FOLDER = cls.root / "logs"

        cls.app = create_app(TemporaryConfig)
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        for handler in cls.app.logger.handlers[:]:
            handler.close()
            cls.app.logger.removeHandler(handler)

        cls.temp_dir.cleanup()

    def make_image(self):
        image = Image.new("RGB", (800, 600), "blue")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    def submit_job(self, module_options=None):
        return self.client.post(
            "/image-studio/api/process",
            data={
                "image": (
                    self.make_image(),
                    "test.png",
                ),
                "module_ids": json.dumps(["image_preprocessor"]),
                "module_options": json.dumps(
                    module_options or {}
                ),
            },
            content_type="multipart/form-data",
        )

    def wait_for_job(self, job_id, timeout=15):
        start = time.time()

        while time.time() - start < timeout:
            response = self.client.get(
                f"/image-studio/api/jobs/{job_id}"
            )

            job = response.get_json()["job"]

            if job["status"] in ("completed", "failed"):
                return job

            time.sleep(0.1)

        self.fail("Image processing job timed out.")

    def test_modules_endpoint(self):
        response = self.client.get("/image-studio/api/modules")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        self.assertTrue(
            any(
                module["id"] == "image_preprocessor"
                for module in response.get_json()["modules"]
            )
        )

    def test_missing_image(self):
        response = self.client.post(
            "/image-studio/api/process",
            data={
                "module_ids": '["image_preprocessor"]',
                "module_options": "{}",
            },
        )

        self.assertEqual(response.status_code, 400)

    def test_unsupported_image(self):
        response = self.client.post(
            "/image-studio/api/process",
            data={
                "image": (io.BytesIO(b"test"), "test.gif"),
                "module_ids": '["image_preprocessor"]',
                "module_options": "{}",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)

    def test_successful_processing(self):
        response = self.submit_job({
            "image_preprocessor": {
                "width": 400,
                "height": 400,
                "fit": "contain",
                "format": "PNG",
            }
        })

        self.assertEqual(response.status_code, 202)

        job_id = response.get_json()["job_id"]
        job = self.wait_for_job(job_id)

        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["progress"], 100)

        result_path = Path(job["result"]["image_path"])
        self.assertTrue(result_path.is_file())

        with Image.open(result_path) as image:
            self.assertEqual(image.size, (400, 300))

        preview = self.client.get(
            f"/image-studio/api/jobs/{job_id}/preview"
        )

        try:
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.mimetype, "image/png")
        finally:
            preview.close()
        self.assertTrue(Path(download.request.path).exists())

        download = self.client.get(
            f"/image-studio/api/jobs/{job_id}/download"
        )

        try:
            self.assertEqual(download.status_code, 200)
            self.assertTrue(
                download.headers["Content-Disposition"].startswith(
                    "attachment"
                )
            )
        finally:
            download.close()
        self.assertTrue(Path(download.request.path).exists())


    def test_unknown_module(self):
        response = self.client.post(
            "/image-studio/api/process",
            data={
                "image": (self.make_image(), "test.png"),
                "module_ids": '["unknown_module"]',
                "module_options": "{}",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 400)

    def test_job_not_found(self):
        response = self.client.get(
            "/image-studio/api/jobs/nonexistent"
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
