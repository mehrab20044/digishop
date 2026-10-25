from django.core.exceptions import ValidationError
from PIL import Image


def validate_avatar(value):
    if value.size > 5 * 1024 * 1024:
        raise ValidationError(
            "حجم تصویر نباید بیشتر از ۵ مگابایت باشد."
        )

    position = value.tell()

    try:
        value.seek(0)

        with Image.open(value) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValidationError(
                    "فرمت تصویر باید JPEG، PNG یا WebP باشد."
                )

            if image.width * image.height > 20_000_000:
                raise ValidationError(
                    "ابعاد تصویر بیش از حد مجاز است."
                )
    except (
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise ValidationError("تصویر نامعتبر است.") from exc
    finally:
        value.seek(position)