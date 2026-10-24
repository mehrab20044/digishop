import warnings

from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError

MAX_PRODUCT_IMAGE_SIZE = 5 * 1024 * 1024
MAX_PRODUCT_IMAGE_PIXELS = 20_000_000


def validate_product_image_size(image):
    if image.size > MAX_PRODUCT_IMAGE_SIZE:
        raise ValidationError(
            "حجم تصویر نباید بیشتر از ۵ مگابایت باشد.",
            code="image_too_large",
        )


def validate_product_image_content(image):
    original_position = image.tell() if hasattr(image, "tell") else 0

    try:
        image.seek(0)

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)

            picture = Image.open(image)

            if picture.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValidationError(
                    "فرمت واقعی تصویر باید JPEG، PNG یا WebP باشد.",
                    code="invalid_image_format",
                )

            if picture.width * picture.height > MAX_PRODUCT_IMAGE_PIXELS:
                raise ValidationError(
                    "ابعاد تصویر نباید بیشتر از ۲۰ میلیون پیکسل باشد.",
                    code="image_dimensions_too_large",
                )

            picture.verify()

            image.seek(0)
            picture = Image.open(image)
            picture.load()

    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValidationError(
            "ابعاد تصویر بیش از حد مجاز است.",
            code="image_dimensions_too_large",
        ) from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationError(
            "فایل تصویر نامعتبر یا خراب است.",
            code="invalid_image",
        ) from exc
    finally:
        image.seek(original_position)
