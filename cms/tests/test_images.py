import io
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.exceptions import ValidationError

from cms.services.image_service import upload_image
from cms.tests.helpers import user


class ImageTests(TestCase):
    def setUp(self):
        self.actor = user(is_staff=True)
        self.directory = tempfile.TemporaryDirectory()
        self.override = override_settings(MEDIA_ROOT=self.directory.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.addCleanup(self.directory.cleanup)

    def test_converts_uploaded_image_to_webp(self):
        output = io.BytesIO()
        Image.new("RGB", (2400, 1000), "red").save(output, "PNG")
        asset = upload_image(self.actor, SimpleUploadedFile("example.png", output.getvalue(), content_type="image/png"))
        self.assertTrue(asset.file.name.endswith(".webp"))
        self.assertEqual(asset.width, 1920)
        self.assertLessEqual(asset.height, 1920)

    def test_rejects_invalid_or_svg(self):
        for name, body in [("invalid.png", b"not image"), ("image.svg", b"<svg></svg>")]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                upload_image(self.actor, SimpleUploadedFile(name, body))

    def test_missing_upload_rejected(self):
        with self.assertRaises(ValidationError):
            upload_image(self.actor, None)
