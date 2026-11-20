
import sys
import time
from pathlib import Path

# Add project root to Python import path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.animation.job_manager import AnimationJobManager


class FakeAnimationEngine:

    def generate(
        self,
        image_path,
        audio_path,
        output_dir,
        options=None,
        progress_callback=None,
        ):
        if progress_callback:
            progress_callback(30, "Preparing animation...")

        time.sleep(1)

        if progress_callback:
            progress_callback(80, "Rendering animation...")

        return {"video": "test-output.mp4"}


def test_animation_job():
    manager = AnimationJobManager(max_workers=1)
    engine = FakeAnimationEngine()

    job_id = manager.submit(
        engine=engine,
        image_path=Path("test-image.png"),
        audio_path=Path("test-audio.wav"),
        output_dir=Path("test-output"),
    )

    print("Job submitted:", job_id)

    try:
        for _ in range(50):
            job = manager.get_job(job_id)

            print(
                "Status:",
                job["status"],
                "| Progress:",
                job["progress"]
            )

            if job["status"] in ("completed", "failed"):
                break

            time.sleep(0.2)

        assert job["status"] == "completed", job
        assert job["progress"] == 100
        assert job["result"]["video"] == "test-output.mp4"

        print("\nSUCCESS: Background job completed correctly.")

    finally:
        manager.executor.shutdown(wait=True)


if __name__ == "__main__":
    test_animation_job()
