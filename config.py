
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = "change-this-local-development-key"

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    UPLOAD_FOLDER = BASE_DIR / "uploads"
    OUTPUT_FOLDER = BASE_DIR / "outputs"
    LOG_FOLDER = BASE_DIR / "logs"

    # SadTalker
    SADTALKER_DIR = BASE_DIR / "SadTalker"
    SADTALKER_CHECKPOINTS = SADTALKER_DIR / "checkpoints"

    VIDEO_SIZE = 256
    VIDEO_PREPROCESS = "full"
    GENERATION_TIMEOUT = 28800  # 8 hours  4 huors 14400 previously 

    # Advanced Animation Engines
    ANIMATION_MODELS_DIR = BASE_DIR / "models"

    ECHOMIMIC_V3_DIR = ANIMATION_MODELS_DIR / "EchoMimicV3"
    ECHOMIMIC_V3_VARIANT = "preview"

    # Legacy local inference settings
    # Actual EchoMimic inference will run on a remote GPU worker.
    ECHOMIMIC_V3_PYTHON = None
    ECHOMIMIC_V3_TIMEOUT = 14400

    # Remote EchoMimic V3 worker
    ECHOMIMIC_WORKER_URL = os.getenv("ECHOMIMIC_WORKER_URL")
    ECHOMIMIC_WORKER_TOKEN = os.getenv("ECHOMIMIC_WORKER_TOKEN")

    ECHOMIMIC_WORKER_TIMEOUT = int(
        os.getenv("ECHOMIMIC_WORKER_TIMEOUT", "14400")
    )

    ECHOMIMIC_WORKER_POLL_INTERVAL = int(
        os.getenv("ECHOMIMIC_WORKER_POLL_INTERVAL", "3")
    )

    ECHOMIMIC_WORKER_CONNECT_TIMEOUT = int(
        os.getenv("ECHOMIMIC_WORKER_CONNECT_TIMEOUT", "30")
    )

    ECHOMIMIC_WORKER_UPLOAD_TIMEOUT = int(
        os.getenv("ECHOMIMIC_WORKER_UPLOAD_TIMEOUT", "300")
    )
