
import shutil
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.modules.base import ProcessingModule


class ImagePreprocessor(ProcessingModule):

    module_id = "image_preprocessor"
    name = "Image Preprocessor"
    description = "Validates, corrects orientation, resizes and converts images."
    version = "1.2"
    category = "image"

    requirements = {
        "gpu": False,
        "minimum_vram_gb": 0,
    }

    options = [
        {"name": "width", "type": "integer", "default": None},
        {"name": "height", "type": "integer", "default": None},
        {
            "name": "fit",
            "type": "select",
            "default": "contain",
            "choices": ["contain", "cover", "stretch"],
        },
        {
            "name": "format",
            "type": "select",
            "default": "original",
            "choices": ["original", "JPEG", "PNG", "WEBP"],
        },
        {"name": "quality", "type": "integer", "default": 95},
    ]

    SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}
    MAX_DIMENSION = 10000
    MAX_PIXELS = 40_000_000

    def __init__(self, config):
        self.config = config

    def is_available(self):
        return True

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

        width = self._dimension(options.get("width"), "width")
        height = self._dimension(options.get("height"), "height")

        fit = options.get("fit", "contain")
        output_format = options.get("format", "original")
        quality = options.get("quality", 95)

        if not isinstance(fit, str) or fit.lower() not in (
            "contain", "cover", "stretch"
        ):
            raise ValueError("Invalid image fit mode.")

        fit = fit.lower()

        if not isinstance(output_format, str):
            raise ValueError("Output format must be a string.")

        output_format = output_format.upper()

        if output_format not in ("ORIGINAL", *self.SUPPORTED_FORMATS):
            raise ValueError("Unsupported output format.")

        if isinstance(quality, bool) or not isinstance(quality, int):
            raise ValueError("Image quality must be an integer.")

        if not 1 <= quality <= 100:
            raise ValueError("Image quality must be between 1 and 100.")

        if progress_callback:
            progress_callback(10, "Loading image.")

        try:
            with Image.open(source) as opened_image:
                source_format = opened_image.format
                original_width, original_height = opened_image.size

                if (
                    original_width > self.MAX_DIMENSION
                    or original_height > self.MAX_DIMENSION
                    or original_width * original_height > self.MAX_PIXELS
                ):
                    raise ValueError(
                        "Image dimensions exceed the supported processing limit."
                    )

                orientation = opened_image.getexif().get(274, 1)

                # Capture metadata before closing the source image.
                source_dpi = opened_image.info.get("dpi")
                source_icc = opened_image.info.get("icc_profile")

                exif = opened_image.getexif()

                # Remove orientation after applying it to the pixels.
                if 274 in exif:
                    del exif[274]

                source_exif = exif.tobytes() if exif else None

                opened_image.load()
                image = ImageOps.exif_transpose(opened_image).copy()

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
            progress_callback(35, "Image loaded and orientation corrected.")

        if width is not None or height is not None:
            if width is None:
                width = max(1, round(image.width * height / image.height))

            if height is None:
                height = max(1, round(image.height * width / image.width))

            target_size = (width, height)

            if fit == "stretch":
                image = image.resize(
                    target_size,
                    Image.Resampling.LANCZOS,
                )
            elif fit == "contain":
                image.thumbnail(
                    target_size,
                    Image.Resampling.LANCZOS,
                )
            else:
                image = ImageOps.fit(
                    image,
                    target_size,
                    method=Image.Resampling.LANCZOS,
                )

        if progress_callback:
            progress_callback(70, "Image resizing completed.")

        if output_format == "ORIGINAL":
            output_format = source_format or "PNG"

        output_format = output_format.upper()

        if output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Cannot preserve the original format ({output_format}). "
                "Choose JPEG, PNG or WEBP instead."
            )

        extension = {
            "JPEG": ".jpg",
            "PNG": ".png",
            "WEBP": ".webp",
        }[output_format]

        supplied_output_dir = input_data.get("output_dir")

        if supplied_output_dir:
            output_root = Path(supplied_output_dir) / "preprocessing"
        else:
            output_root = (
                Path(self.config["OUTPUT_FOLDER"]) / "image_processing"
            )

        output_dir = output_root / uuid4().hex
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / f"{source.stem}_processed{extension}"

        # Avoid re-encoding when the original image needs no changes.
        if (
            output_format == source_format
            and width is None
            and height is None
            and orientation in (None, 1)
        ):
            shutil.copy2(source, output_path)

            if progress_callback:
                progress_callback(
                    100,
                    "Original image preserved without re-encoding.",
                )

            result = {
                "image_path": str(output_path),
                "format": output_format,
                "width": image.width,
                "height": image.height,
                "size_bytes": output_path.stat().st_size,
                "dpi": source_dpi,
                "preserved_original": True,
            }

            input_data.set("image_path", str(output_path))
            return result

        has_transparency = (
            "A" in image.getbands()
            or "transparency" in image.info
        )

        if output_format == "JPEG":
            if image.mode not in ("RGB", "L") or has_transparency:
                rgba_image = image.convert("RGBA")
                background = Image.new(
                    "RGB",
                    rgba_image.size,
                    (255, 255, 255),
                )
                background.paste(
                    rgba_image,
                    mask=rgba_image.getchannel("A"),
                )
                image = background

        elif output_format == "PNG":
            if image.mode not in ("RGB", "RGBA", "L", "LA", "P"):
                image = image.convert("RGBA")

        elif output_format == "WEBP":
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")

        save_options = {}

        if output_format in ("JPEG", "WEBP"):
            save_options["quality"] = quality

        if output_format == "JPEG":
            save_options["subsampling"] = 0
            save_options["optimize"] = True

        if source_dpi:
            save_options["dpi"] = source_dpi

        if source_icc:
            save_options["icc_profile"] = source_icc

        if source_exif:
            save_options["exif"] = source_exif

        image.save(
            output_path,
            format=output_format,
            **save_options,
        )

        if progress_callback:
            progress_callback(100, "Image preprocessing completed.")

        result = {
            "image_path": str(output_path),
            "format": output_format,
            "width": image.width,
            "height": image.height,
            "size_bytes": output_path.stat().st_size,
            "dpi": source_dpi,
            "preserved_original": False,
        }

        input_data.set("image_path", str(output_path))

        return result

    @classmethod
    def _dimension(cls, value, name):
        if value is None:
            return None

        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} must be an integer.")

        if not 1 <= value <= cls.MAX_DIMENSION:
            raise ValueError(
                f"{name} must be between 1 and {cls.MAX_DIMENSION}."
            )

        return value
