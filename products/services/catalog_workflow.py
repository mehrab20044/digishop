"""Transactional application services for the guided catalog workspace.

Views own authorization; these functions own payload validation, row locks and
business rules. Existing stock, SKU IDs and order references are never replaced.
"""

from itertools import product as cartesian_product
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from products.models import Brand, Product
from products.services.attribute_service import (
    bump,
    check_revision,
    save_axes,
    save_specs,
    save_variant,
    validate_axes,
    validate_options,
    validate_product_specs,
)
from products.services.category_service import category_tree_write_lock

BASIC_FIELDS = {
    "name",
    "slug",
    "category_id",
    "brand_id",
    "short_description",
    "long_description_html",
    "gallery_description_html",
}


def integer(value, label, minimum=0, maximum=9007199254740991):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValidationError({label: "عدد صحیح معتبر وارد کنید."})
    return value


def new_slug(model, name, limit):
    base = slugify(name, allow_unicode=True)[: limit - 14].strip("-") or "item"
    # A random suffix makes concurrent creates safe without sequence scans.
    return base + "-" + uuid4().hex[:12]


def save_brand(data, brand_id=None):
    if (
        not isinstance(data, dict)
        or set(data) - {"name", "slug"}
        or not isinstance(data.get("name"), str)
        or not data["name"].strip()
        or ("slug" in data and not isinstance(data["slug"], str))
    ):
        raise ValidationError({"name": "نام برند الزامی است."})
    with transaction.atomic():
        brand = (
            Brand.objects.select_for_update().get(pk=brand_id) if brand_id else Brand()
        )
        brand.name = data["name"].strip()
        brand.slug = (
            data.get("slug", "").strip()
            or brand.slug
            or new_slug(Brand, brand.name, 170)
        )
        brand.full_clean()
        brand.save()
        return brand


def save_basic(data, product_id=None, revision=None):
    if not isinstance(data, dict) or set(data) - BASIC_FIELDS:
        raise ValidationError("ساختار اطلاعات محصول معتبر نیست.")
    with category_tree_write_lock():
        item = (
            Product.objects.select_for_update().get(pk=product_id)
            if product_id
            else Product(status=Product.Status.DRAFT, is_active=False, price=0, stock=0)
        )
        if product_id:
            check_revision(item, revision)
        for name, value in data.items():
            if name.endswith("_id"):
                if name == "brand_id" and value is None:
                    pass
                else:
                    integer(value, name, 1, 2147483647)
            elif not isinstance(value, str):
                raise ValidationError({name: "متن معتبر وارد کنید."})
            setattr(item, name, value)
        item.name = (item.name or "").strip()
        if not item.slug:
            item.slug = new_slug(Product, item.name, 220)
        # A category change must not silently discard existing specifications.
        if item.pk:
            validate_product_specs(
                item, require_all=item.status == Product.Status.PUBLISHED
            )
        item.full_clean()
        item.save()
        bump(item)
        return item


def preview_combinations(axes):
    validate_axes(axes)
    if not axes:
        raise ValidationError("ابتدا گزینه‌هایی مانند سایز یا رنگ بسازید.")
    count = 1
    for axis in axes:
        count *= len(axis["values"])
        if count > 200:
            raise ValidationError(
                "هر بار حداکثر ۲۰۰ ترکیب بسازید؛ گزینه‌های انتخاب‌شده را کمتر کنید."
            )
    return [
        dict(zip([a["key"] for a in axes], values, strict=True))
        for values in cartesian_product(*(a["values"] for a in axes))
    ]


def save_combinations(product_id, revision, axes, rows):
    """Save schema and a deliberate subset of rows together; rollback on any error.

    Omitted existing rows stay untouched. Existing IDs cannot change options.
    Every stock update requires the stock originally observed by the editor.
    """
    if not isinstance(rows, list) or not 1 <= len(rows) <= 200:
        raise ValidationError("بین یک تا ۲۰۰ ردیف قیمت و موجودی ارسال کنید.")
    with transaction.atomic():
        item = Product.objects.select_for_update().get(pk=product_id)
        check_revision(item, revision)
        item = save_axes(item.pk, item.catalog_revision, axes)
        seen_ids, seen_options = set(), set()
        for index, submitted in enumerate(rows, 1):
            try:
                if not isinstance(submitted, dict):
                    raise ValidationError("ردیف معتبر نیست.")
                row = dict(submitted)
                ident = row.pop("id", None)
                if ident is not None:
                    integer(ident, "id", 1, 2147483647)
                    if ident in seen_ids:
                        raise ValidationError("شناسهٔ تنوع تکراری است.")
                    seen_ids.add(ident)
                options, fingerprint = validate_options(axes, row.get("options"))
                if fingerprint in seen_options:
                    raise ValidationError("ترکیب گزینه‌ها تکراری است.")
                seen_options.add(fingerprint)
                if ident is not None:
                    old = item.variants.select_for_update().get(pk=ident)
                    if old.options != options:
                        raise ValidationError(
                            "گزینه‌های یک SKU موجود را عوض نکنید؛ ترکیب جدید بسازید."
                        )
                if not row.get("sku") and ident is None:
                    row["sku"] = f"P{item.pk}-" + uuid4().hex[:14].upper()
                item = save_variant(item.pk, item.catalog_revision, row, ident)
            except ValidationError as exc:
                raise ValidationError({f"ردیف {index}": exc.messages}) from exc
        return item


def save_simple(product_id, revision, data):
    if not isinstance(data, dict) or set(data) != {"price", "stock", "expected_stock"}:
        raise ValidationError("اطلاعات قیمت و موجودی معتبر نیست.")
    with transaction.atomic():
        item = Product.objects.select_for_update().get(pk=product_id)
        check_revision(item, revision)
        if item.variants.exists() or item.variant_schema:
            raise ValidationError(
                "این محصول تنوع دارد؛ قیمت و موجودی را در جدول تنوع‌ها تغییر دهید."
            )
        if (
            type(data["expected_stock"]) is not int
            or data["expected_stock"] != item.stock
        ):
            raise ValidationError("موجودی تغییر کرده است؛ اطلاعات تازه را دریافت کنید.")
        item.price = integer(data["price"], "price", 1)
        item.stock = integer(data["stock"], "stock", 0, 2147483647)
        item.full_clean()
        item.save(update_fields=["price", "stock"])
        bump(item)
        return item


def readiness(item):
    issues = []
    if not item.name.strip() or not item.category_id:
        issues.append({"step": 0, "message": "نام و دسته‌بندی را کامل کنید."})
    if not item.images.filter(is_primary=True).exists():
        issues.append({"step": 1, "message": "حداقل یک تصویر اصلی اضافه کنید."})
    try:
        validate_product_specs(item, require_all=True)
    except ValidationError as exc:
        issues.append({"step": 2, "message": "، ".join(exc.messages)})
    if item.variants.exists():
        active = list(item.variants.filter(is_active=True))
        if not active:
            issues.append({"step": 3, "message": "حداقل یک تنوع فعال لازم است."})
        for variant in active:
            try:
                variant.full_clean()
            except ValidationError as exc:
                issues.append(
                    {"step": 3, "message": f"{variant.sku}: " + "، ".join(exc.messages)}
                )
    elif item.variant_schema or item.price <= 0:
        issues.append({"step": 3, "message": "قیمت محصول یا جدول تنوع‌ها را کامل کنید."})
    # Zero stock is allowed: published unavailable products remain discoverable.
    return issues


def set_publication(product_id, revision, mode):
    if mode not in {"draft", "published", "hidden"}:
        raise ValidationError("وضعیت انتشار معتبر نیست.")
    with category_tree_write_lock():
        item = Product.objects.select_for_update().get(pk=product_id)
        check_revision(item, revision)
        if mode == "published":
            issues = readiness(item)
            if issues:
                raise ValidationError(
                    {"انتشار": [issue["message"] for issue in issues]}
                )
        item.status = (
            Product.Status.DRAFT if mode == "draft" else Product.Status.PUBLISHED
        )
        item.is_active = mode == "published"
        # Hiding must remain possible even when old catalog data needs repair.
        if mode == "published":
            item.full_clean()
        item.save(update_fields=["status", "is_active"])
        bump(item)
        return item


# Keep the existing typed-specification service available to other entry points.
save_specifications = save_specs


def catalog_summary(item):
    variants = list(item.variants.all())
    active = [variant for variant in variants if variant.is_active]
    prices = [variant.price for variant in active if variant.price > 0]
    return {
        "has_variants": bool(variants),
        "variant_count": len(variants),
        "total_stock": sum(variant.stock for variant in active)
        if variants
        else item.stock,
        "min_price": min(prices) if prices else (None if variants else item.price),
        "max_price": max(prices) if prices else (None if variants else item.price),
    }
