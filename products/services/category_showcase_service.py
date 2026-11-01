import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import FileExtensionValidator
from django.db import transaction
from django.shortcuts import get_object_or_404
from products.models import Category
from products.services.category_service import category_tree_write_lock
from products.services.image_service import prepare_product_image
from products.validators import (
    validate_product_image_content,
    validate_product_image_size,
)
from rest_framework.exceptions import APIException, ValidationError

logger = logging.getLogger(__name__)


class StaleSelection(APIException):
    status_code = 409
    default_detail = "انتخاب صفحه اصلی تغییر کرده؛ فهرست را دوباره دریافت کنید."


def category_image_url(name):
    return Category._meta.get_field("image").storage.url(name) if name else None


def home_category_ids():
    return list(
        Category.objects.filter(is_home_featured=True)
        .order_by("home_featured_order", "pk")
        .values_list("pk", flat=True)
    )


def set_home_categories(ids, expected_ids):
    if (
        not isinstance(ids, list)
        or len(ids) != 5
        or any(type(pk) is not int or pk <= 0 for pk in ids)
        or len(set(ids)) != 5
    ):
        raise ValidationError({"category_ids": "دقیقاً پنج دسته متفاوت انتخاب کنید."})
    if not isinstance(expected_ids, list) or any(
        type(pk) is not int for pk in expected_ids
    ):
        raise ValidationError({"expected_ids": "نسخه فعلی انتخاب‌ها را ارسال کنید."})
    with category_tree_write_lock():
        if home_category_ids() != expected_ids:
            raise StaleSelection()
        rows = {
            c.pk: c for c in Category.objects.select_for_update().filter(pk__in=ids)
        }
        if set(rows) != set(ids):
            raise ValidationError({"category_ids": "یکی از دسته‌ها دیگر وجود ندارد."})
        missing = [rows[pk].name for pk in ids if not rows[pk].image]
        if missing:
            raise ValidationError(
                {
                    "category_ids": "ابتدا عکس این دسته‌ها را بارگذاری کنید: "
                    + "، ".join(missing)
                }
            )
        Category.objects.filter(is_home_featured=True).update(is_home_featured=False, home_featured_order=0)
        for position, pk in enumerate(ids, 1):
            Category.objects.filter(pk=pk).update(is_home_featured=True, home_featured_order=position)
    return ids


def replace_category_image(*, category_id, upload, audit=None):
    if upload is not None:
        try:
            FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "webp"])(
                upload
            )
            validate_product_image_size(upload)
            validate_product_image_content(upload)
            prepared = prepare_product_image(upload, max_dimensions=(640, 640))
        except DjangoValidationError as exc:
            raise ValidationError({"image": exc.messages}) from exc
        except (OSError, ValueError, SyntaxError) as exc:
            raise ValidationError({"image": "پردازش تصویر ممکن نیست."}) from exc
    stored = None
    try:
        with category_tree_write_lock():
            category = get_object_or_404(
                Category.objects.select_for_update(), pk=category_id
            )
            if upload is None and category.is_home_featured:
                raise ValidationError(
                    {
                        "image": "این دسته در صفحه اصلی است؛ عکس را جایگزین کنید یا اول دسته دیگری برای صفحه اصلی انتخاب کنید."
                    }
                )
            old_name = category.image.name
            storage = category.image.storage
            if upload is None:
                new_name = ""
            else:
                category.image.save(prepared.name, prepared, save=False)
                new_name = category.image.name
                stored = (storage, new_name)
            # Media changes must not trigger category URL rewrites.
            Category.objects.filter(pk=category.pk).update(image=new_name)
            category.image.name = new_name
            if audit:
                audit(category)
            if old_name and old_name != new_name:

                def remove_old():
                    try:
                        if not Category.objects.filter(image=old_name).exists():
                            storage.delete(old_name)
                    except Exception:
                        logger.exception("Could not delete an old category image")

                transaction.on_commit(remove_old)
            return category
    except Exception:
        if stored:
            try:
                stored[0].delete(stored[1])
            except Exception:
                logger.exception("Could not clean up category image upload")
        raise
