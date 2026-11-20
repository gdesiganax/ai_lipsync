
from io import BytesIO
from pathlib import Path
from threading import Lock
from uuid import uuid4

from PIL import Image, UnidentifiedImageError

from app.services.modules.base import ProcessingModule


# Reuse loaded ONNX sessions across processing jobs.
_MODEL_SESSIONS = {}
_MODEL_LOCK = Lock()


class BackgroundRemover(ProcessingModule):

    module_id = "background_remover"
    name = "Background Remover"
    description = "Removes image backgrounds and produces transparent PNG images."
    version = "1.0"
    category = "image"

    requirements = {
        "gpu": False,
        "minimum_vram_gb": 0,
    }

    options = [
        {
            "name": "model",
            "type": "select",
            "default": "u2net",
            "choices": ["u2net", "u2netp"],
        },
    ]

    MAX_DIMENSION = 10000
    MAX_PIXELS = 40_000_000

    def __init__(self, config):
        self.config = config

    def is_available(self):
        try:
            import rembg
            import onnxruntime
            return True
        except ImportError:
            return False

    @staticmethod
    def _get_session(model_name):
        from rembg import new_session

        with _MODEL_LOCK:
            if model_name not in _MODEL_SESSIONS:
                _MODEL_SESSIONS[model_name] = new_session(
                    model_name,
                    providers=["CPUExecutionProvider"],
                )

            return _MODEL_SESSIONS[model_name]

    def process(self, input_data, options=None, progress_callback=None):
        if options is None:
            options = {}

        if not isinstance(options, dict):
            raise TypeError("Image processing options must be a dictionary.")

        image_path = input_data.get("image_path")

        if not image_path:
            raise ValueError("No image_path provided.")

        source = Path(image_path)

        if not source.is_file():
            raise FileNotFoundError(f"Image file not found: {source}")

        model_name = options.get("model", "u2net")

        if model_name not in ("u2net", "u2netp"):
            raise ValueError("Unsupported background removal model.")

        if not self.is_available():
            raise RuntimeError(
                "Background removal dependencies are not installed. "
                "Install rembg and onnxruntime."
            )

        if progress_callback:
            progress_callback(10, "Validating input image.")

        try:
            with Image.open(source) as opened_image:
                if (
                    opened_image.width > self.MAX_DIMENSION
                    or opened_image.height > self.MAX_DIMENSION
                    or opened_image.width * opened_image.height > self.MAX_PIXELS
                ):
                    raise ValueError(
                        "Image dimensions exceed the supported processing limit."
                    )

                opened_image.load()

                source_dpi = opened_image.info.get("dpi")
                source_icc = opened_image.info.get("icc_profile")

        except ValueError:
            raise
        except (
            UnidentifiedImageError,
            OSError,
            Image.DecompressionBombError,
        ) as error:
            raise ValueError(
                "The uploaded file is not a valid or supported image."
            ) from error

        if progress_callback:
            progress_callback(20, "Preparing background removal model.")

        try:
            session = self._get_session(model_name)

            if progress_callback:
                progress_callback(35, "Removing image background.")

            from rembg import remove

            output_bytes = remove(
                source.read_bytes(),
                session=session,
            )

        except Exception as error:
            raise RuntimeError(
                f"Background removal failed: {error}"
            ) from error

        if progress_callback:
            progress_callback(85, "Preparing transparent PNG.")

        try:
            with Image.open(BytesIO(output_bytes)) as processed_image:
                processed_image.load()
                result_image = processed_image.convert("RGBA")

        except (UnidentifiedImageError, OSError) as error:
            raise RuntimeError(
                "Background removal did not produce a valid image."
            ) from error

        supplied_output_dir = input_data.get("output_dir")

        if supplied_output_dir:
            output_root = Path(supplied_output_dir) / "background_removal"
        else:
            output_root = (
                Path(self.config["OUTPUT_FOLDER"]) / "image_processing"
            )

        output_dir = output_root / uuid4().hex
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{source.stem}_no_background.png"

        save_options = {"optimize": True}

        if source_dpi:
            save_options["dpi"] = source_dpi

        if source_icc:
            save_options["icc_profile"] = source_icc

        result_image.save(
            output_path,
            format="PNG",
            **save_options,
        )

        if progress_callback:
            progress_callback(100, "Background removal completed.")

        result = {
            "image_path": str(output_path),
            "format": "PNG",
            "width": result_image.width,
            "height": result_image.height,
            "size_bytes": output_path.stat().st_size,
            "model": model_name,
            "transparent": True,
        }

        input_data.set("image_path", str(output_path))

        return result
