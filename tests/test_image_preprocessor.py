
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from app import create_app
from app.services.modules.context import ProcessingContext


class ImagePreprocessorTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.module = cls.app.extensions[
            "processing_module_registry"
        ].get("image_preprocessor")

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.source = self.root / "test_image.png"
        Image.new("RGB", (800, 600), "red").save(self.source)

        self.config = dict(self.app.config)
        self.config["OUTPUT_FOLDER"] = str(self.root / "outputs")

        from app.services.modules.processors.image_preprocessor import (
            ImagePreprocessor,
        )

        self.module = ImagePreprocessor(self.config)

    def tearDown(self):
        self.temp_dir.cleanup()

    def process(self, options=None, image_path=None):
        context = ProcessingContext({
            "image_path": str(image_path or self.source),
        })

        result = self.module.process(context, options or {})
        return context, result

    def test_basic_processing(self):
        context, result = self.process()

        self.assertTrue(Path(result["image_path"]).is_file())
        self.assertEqual(result["width"], 800)
        self.assertEqual(result["height"], 600)
        self.assertEqual(result["format"], "PNG")
        self.assertEqual(context.get("image_path"), result["image_path"])

    def test_contain_resize(self):
        _, result = self.process({
            "width": 400,
            "height": 400,
            "fit": "contain",
        })

        self.assertEqual((result["width"], result["height"]), (400, 300))

    def test_cover_resize(self):
        _, result = self.process({
            "width": 400,
            "height": 400,
            "fit": "cover",
        })

        self.assertEqual((result["width"], result["height"]), (400, 400))

    def test_stretch_resize(self):
        _, result = self.process({
            "width": 400,
            "height": 400,
            "fit": "stretch",
        })

        self.assertEqual((result["width"], result["height"]), (400, 400))

    def test_width_only_preserves_aspect_ratio(self):
        _, result = self.process({"width": 400})

        self.assertEqual((result["width"], result["height"]), (400, 300))

    def test_height_only_preserves_aspect_ratio(self):
        _, result = self.process({"height": 300})

        self.assertEqual((result["width"], result["height"]), (400, 300))

    def test_jpeg_conversion(self):
        _, result = self.process({"format": "JPEG"})

        self.assertEqual(result["format"], "JPEG")
        self.assertTrue(result["image_path"].endswith(".jpg"))

    def test_webp_conversion(self):
        _, result = self.process({"format": "WEBP"})

        self.assertEqual(result["format"], "WEBP")
        self.assertTrue(result["image_path"].endswith(".webp"))

    def test_transparent_png_to_jpeg(self):
        transparent_image = self.root / "transparent.png"
        Image.new("RGBA", (100, 100), (255, 0, 0, 0)).save(
            transparent_image
        )

        _, result = self.process(
            {"format": "JPEG"},
            transparent_image,
        )

        with Image.open(result["image_path"]) as output:
            self.assertEqual(output.mode, "RGB")
            self.assertEqual(output.getpixel((50, 50)), (255, 255, 255))

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            self.process(image_path=self.root / "missing.png")

    def test_invalid_image(self):
        invalid_file = self.root / "invalid.png"
        invalid_file.write_text("not an image")

        with self.assertRaises(ValueError):
            self.process(image_path=invalid_file)

    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            self.process({"width": 0})

    def test_invalid_format(self):
        with self.assertRaises(ValueError):
            self.process({"format": "GIF"})

    def test_invalid_quality(self):
        with self.assertRaises(ValueError):
            self.process({"quality": 101})

    def test_invalid_options_type(self):
        with self.assertRaises(TypeError):
            self.module.process(
                ProcessingContext({"image_path": str(self.source)}),
                ["invalid"],
            )

    def test_progress_callback(self):
        progress = []

        context = ProcessingContext({
            "image_path": str(self.source),
        })

        self.module.process(
            context,
            progress_callback=lambda percent, message: progress.append(
                (percent, message)
            ),
        )

        self.assertTrue(progress)
        self.assertEqual(progress[-1][0], 100)

    def test_unique_output_directories(self):
        _, first = self.process()
        _, second = self.process()

        self.assertNotEqual(first["image_path"], second["image_path"])
        self.assertTrue(Path(first["image_path"]).is_file())
        self.assertTrue(Path(second["image_path"]).is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
