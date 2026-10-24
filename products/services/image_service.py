import uuid
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MAX_PRODUCT_IMAGE_DIMENSIONS = (1600, 1600)
PRODUCT_IMAGE_QUALITY = 85


def prepare_product_image(image):
    """Normalize a validated product upload for efficient display."""
    original_position = image.tell()

    try:
        image.seek(0)
        with Image.open(image) as source:
            picture = ImageOps.exif_transpose(source)
            picture.thumbnail(MAX_PRODUCT_IMAGE_DIMENSIONS, Image.Resampling.LANCZOS)

            has_transparency = picture.mode in {"RGBA", "LA"} or (
                picture.mode == "P" and "transparency" in picture.info
            )
            output_mode = "RGBA" if has_transparency else "RGB"
            if picture.mode != output_mode:
                picture = picture.convert(output_mode)

            output = BytesIO()
            picture.save(
                output,
                format="WEBP",
                quality=PRODUCT_IMAGE_QUALITY,
                method=6,
            )
    finally:
        image.seek(original_position)

    return ContentFile(
        output.getvalue(),
        name=f"{uuid.uuid4().hex}.webp",
    )
