
import sys
import time
import tempfile
from pathlib import Path
from io import BytesIO
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.services.animation.base import AnimationEngine
from app.services.animation.registry import EngineRegistry


class FakeAnimationEngine(AnimationEngine):

    engine_id = "test_engine"
    name = "Test Animation Engine"
    description = "Simulated engine for API testing."

    def is_available(self):
        return True

    def generate(self, image_path, audio_path, output_dir, options=None, progress_callback=None,):
        if progress_callback:
            progress_callback(20, "Preparing animation...")

        time.sleep(1)

        if progress_callback:
            progress_callback(75, "Rendering animation...")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        video_path = output_dir / "test-output.mp4"
        video_path.write_bytes(b"FAKE MP4 CONTENT")

        if progress_callback:
            progress_callback(95, "Finalizing video...")

        return {
            "video_path": str(video_path),
            "message": "Test animation generated.",
            }

def test_animation_api():

    with tempfile.TemporaryDirectory() as temp_dir:

        temp_path = Path(temp_dir)

        app = create_app()

        app.config["TESTING"] = True
        app.config["UPLOAD_FOLDER"] = temp_path / "uploads"
        app.config["OUTPUT_FOLDER"] = temp_path / "outputs"

        app.config["UPLOAD_FOLDER"].mkdir(parents=True)
        app.config["OUTPUT_FOLDER"].mkdir(parents=True)

        registry = EngineRegistry()
        registry.register(FakeAnimationEngine())

        with patch(
            "app.routes.animation.get_engine_registry",
            return_value=registry
        ):

            client = app.test_client()

            # Submit animation generation request.
            response = client.post(
                "/animation/api/generate",
                data={
                    "engine": "test_engine",
                    "image": (BytesIO(b"fake image"), "test.png"),
                    "audio": (BytesIO(b"fake audio"), "test.wav"),
                },
                content_type="multipart/form-data"
            )

            assert response.status_code == 202, response.json

            job_id = response.json["job_id"]

            print("Job submitted:", job_id)

            # Poll job status.
            for attempt in range(30):

                response = client.get(
                    f"/animation/api/jobs/{job_id}"
                )

                assert response.status_code == 200

                job = response.json["job"]

                print("Job status:", job["status"])

                if job["status"] in ("completed", "failed"):
                    break

                time.sleep(0.2)

            assert job["status"] == "completed", job

            assert job["progress"] == 100

            assert job["result"]["video_path"].endswith(
                "test-output.mp4"
            )

            # Test generated video delivery.
            video_response = client.get(
                f"/animation/api/jobs/{job_id}/video"
            )

            assert video_response.status_code == 200
            assert video_response.mimetype == "video/mp4"
            assert video_response.data == b"FAKE MP4 CONTENT"

            print("Video delivery: SUCCESS")

            print("\nSUCCESS: Animation API workflow passed.")
            video_response.close()


def test_unavailable_engine():
    app = create_app()
    client = app.test_client()

    response = client.post(
        "/animation/api/generate",
        data={
            "engine": "echomimic_v3",
            "image": (BytesIO(b"fake image"), "test.png"),
            "audio": (BytesIO(b"fake audio"), "test.wav"),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 503
    assert response.get_json()["success"] is False

    print("Unavailable engine test: SUCCESS")


def test_missing_image():
    app = create_app()
    client = app.test_client()

    response = client.post(
        "/animation/api/generate",
        data={
            "engine": "echomimic_v3",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert "source image" in response.get_json()["message"].lower()

    print("Missing image validation test: SUCCESS")


if __name__ == "__main__":
    test_animation_api()
    test_unavailable_engine()
    test_missing_image()

    print("\nSUCCESS: All animation API tests passed.")
