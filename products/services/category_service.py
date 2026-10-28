from contextlib import contextmanager

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, connection, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from products.models import Category

CATEGORY_LOCK_NAMESPACE = 72401
CATEGORY_LOCK_KEY = 1

EDITABLE_FIELDS = {
    "name",
    "slug",
    "description",
    "sort_order",
    "parent_id",
    "related_category_ids",
}


@contextmanager
def category_tree_write_lock():
    """
    Acquire before reading or locking categories for a structural change.

    All category-writing entry points must follow this convention.
    The lock is released when the surrounding transaction ends.
    """
    with transaction.atomic():
        if connection.vendor != "postgresql":
            raise RuntimeError(
                "Category tree writes require PostgreSQL."
            )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [CATEGORY_LOCK_NAMESPACE, CATEGORY_LOCK_KEY],
            )

        yield


def _positive_id(value, field):
    if type(value) is not int or value <= 0:
        raise ValidationError({
            field: "شناسه باید عدد صحیح مثبت باشد.",
        })

    return value


def _related_ids(value):
    if not isinstance(value, list):
        raise ValidationError({
            "related_category_ids": "فهرست شناسه‌های دسته‌ها را ارسال کنید.",
        })

    return {
        _positive_id(item, "related_category_ids")
        for item in value
    }


def _model_error(exc):
    if hasattr(exc, "message_dict"):
        return exc.message_dict

    return {"detail": exc.messages}


def save_category(*, data, category_id=None):
    if not isinstance(data, dict):
        raise ValidationError({
            "detail": "اطلاعات باید یک شیء JSON باشد.",
        })

    unknown = set(data) - EDITABLE_FIELDS

    if unknown:
        raise ValidationError({
            "detail": "فیلد غیرمجاز: " + ", ".join(sorted(unknown)),
        })

    if not data:
        raise ValidationError({
            "detail": "اطلاعاتی برای ذخیره ارسال نشده است.",
        })

    if category_id is not None:
        category_id = _positive_id(category_id, "category_id")

    if "parent_id" in data and data["parent_id"] is not None:
        _positive_id(data["parent_id"], "parent_id")

    if "sort_order" in data:
        if type(data["sort_order"]) is not int or data["sort_order"] < 0:
            raise ValidationError({
                "sort_order": "ترتیب نمایش باید عدد صحیح نامنفی باشد.",
            })

    related_ids = None

    if "related_category_ids" in data:
        related_ids = _related_ids(data["related_category_ids"])

    with category_tree_write_lock():
        if category_id is None:
            category = Category()
        else:
            category = get_object_or_404(
                Category.objects.select_for_update(),
                pk=category_id,
            )

        for field in (
            "name",
            "slug",
            "description",
            "sort_order",
            "parent_id",
        ):
            if field in data:
                setattr(category, field, data[field])

        if related_ids is not None:
            if category.pk is not None and category.pk in related_ids:
                raise ValidationError({
                    "related_category_ids": (
                        "دسته نمی‌تواند با خودش ارتباط داشته باشد."
                    ),
                })

            existing_ids = set(
                Category.objects.filter(
                    pk__in=related_ids,
                ).values_list("pk", flat=True)
            )

            if existing_ids != related_ids:
                raise ValidationError({
                    "related_category_ids": (
                        "یک یا چند دستهٔ مرتبط وجود ندارند."
                    ),
                })

        try:
            # A savepoint ensures validation failures roll back all writes.
            with transaction.atomic():
                category.full_clean()
                category.save()

                if related_ids is not None:
                    if category.pk in related_ids:
                        raise ValidationError({
                            "related_category_ids": (
                                "دسته نمی‌تواند با خودش ارتباط داشته باشد."
                            ),
                        })

                    category.related_categories.set(related_ids)

        except DjangoValidationError as exc:
            raise ValidationError(_model_error(exc)) from exc
        except IntegrityError as exc:
            raise ValidationError({
                "detail": (
                    "ذخیره به دلیل تداخل داده‌ها انجام نشد؛ "
                    "نام و نامک را بررسی کنید."
                ),
            }) from exc

        return category