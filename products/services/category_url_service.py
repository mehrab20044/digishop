import re
import unicodedata

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from products.models import Category, CategoryURL

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩كي", "01234567890123456789کی")
PREFIX = "/products/category/"


def normalize_slug(value):
    value = unicodedata.normalize("NFKC", str(value)).translate(DIGITS)
    value = re.sub(r"[\s\u200c\u200d_]+", "-", value)
    return slugify(value, allow_unicode=True).strip("-")[:110].rstrip("-")


def prepare_slug(category):
    if category.slug:
        # Existing slugs remain stable; an explicitly changed slug is normalized.
        previous = Category.objects.filter(pk=category.pk).values_list("slug", flat=True).first() if category.pk else None
        if category.slug != previous:
            category.slug = normalize_slug(category.slug)
        if not category.slug:
            raise ValidationError({"slug": "نامک معتبر وارد کنید."})
        return
    base = normalize_slug(category.name)
    if not base:
        raise ValidationError({"name": "نام دسته باید حرف یا عدد داشته باشد."})
    candidate = base
    suffix = 2
    while Category.objects.exclude(pk=category.pk).filter(slug=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    category.slug = candidate


def paths_for(rows):
    by_id = {row["id"]: row for row in rows}
    result = {}
    for row in rows:
        parts = []
        seen = set()
        current = row
        while current is not None:
            if current["id"] in seen:
                raise ValidationError("ساختار دسته‌ها چرخه دارد.")
            seen.add(current["id"])
            parts.append(current["slug"])
            parent = current["parent_id"]
            if parent is not None and parent not in by_id:
                raise ValidationError("والد دسته پیدا نشد.")
            current = by_id.get(parent)
        path = "/".join(reversed(parts))
        if len(path) > 2048:
            raise ValidationError("مسیر دسته بیش از حد طولانی است.")
        result[row["id"]] = path
    return result


def current_paths():
    return paths_for(Category.objects.values("id", "slug", "parent_id"))


def remember(paths):
    for category_id, path in paths.items():
        alias, _ = CategoryURL.objects.get_or_create(path=path, defaults={"category_id": category_id})
        if alias.category_id != category_id:
            raise ValidationError({"slug": "این آدرس قبلاً متعلق به دستهٔ دیگری بوده؛ نامک دیگری انتخاب کنید."})


def save_with_urls(instance, parent_save, args, kwargs):
    from products.services.category_service import category_tree_write_lock
    with category_tree_write_lock(), transaction.atomic():
        prepare_slug(instance)
        instance.clean()
        remember(current_paths())
        result = parent_save(*args, **kwargs)
        remember(current_paths())
        return result


def resolve_path(path):
    paths = current_paths()
    reverse = {value: key for key, value in paths.items()}
    category_id = reverse.get(path)
    if category_id is None:
        category_id = CategoryURL.objects.filter(path=path).values_list("category_id", flat=True).first()
    if category_id not in paths:
        return None
    category = Category.objects.get(pk=category_id)
    return category, paths[category_id]
