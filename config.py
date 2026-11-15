from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = "change-this-local-development-key"

    MAX_CONTENT_LENGTH = 100 * 1024 * 1024

    UPLOAD_FOLDER = BASE_DIR / "uploads"
    OUTPUT_FOLDER = BASE_DIR / "outputs"
    LOG_FOLDER = BASE_DIR / "logs"

    SADTALKER_DIR = BASE_DIR / "SadTalker"
    SADTALKER_CHECKPOINTS = SADTALKER_DIR / "checkpoints"

    VIDEO_SIZE = 256
    VIDEO_PREPROCESS = "crop"

    GENERATION_TIMEOUT = 14400