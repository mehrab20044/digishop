import io
import uuid
import warnings

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError

from cms.models import PageImage


def upload_image(actor, upload):
    if upload is None or upload.size > 5 * 1024 * 1024:
        raise ValidationError({"image": "یک تصویر حداکثر ۵ مگابایت انتخاب کنید."})
    content = upload.read(5 * 1024 * 1024 + 1)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as original:
                if original.format not in {"JPEG", "PNG", "WEBP"} or original.width * original.height > 20000000:
                    raise ValueError("Unsupported image")
                original.load()
                image = ImageOps.exif_transpose(original).convert("RGBA" if "A" in original.getbands() else "RGB")
                image.thumbnail((1920, 1920))
                output = io.BytesIO()
                image.save(output, "WEBP", quality=85)
                width, height = image.size
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError({"image": "تصویر معتبر JPG، PNG یا WebP انتخاب کنید."}) from exc
    asset = PageImage(width=width, height=height, uploaded_by=actor)
    try:
        asset.file.save(f"{uuid.uuid4().hex}.webp", ContentFile(output.getvalue()), save=False)
        asset.save()
    except Exception:
        if asset.file.name:
            asset.file.delete(save=False)
        raise
    return asset
