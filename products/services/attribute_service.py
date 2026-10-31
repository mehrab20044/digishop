"""Catalog specification and generic SKU rules, shared by owner API and Admin."""
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from products.models import (
    Category,
    CategoryAttribute,
    Product,
    ProductAttributeValue,
    ProductVariant,
)
from products.services.category_service import category_tree_write_lock

DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def validate_definition(attribute):
    if not isinstance(attribute.name, str) or not attribute.name.strip():
        raise ValidationError("نام ویژگی الزامی است.")
    attribute.name = attribute.name.strip()
    if not isinstance(attribute.value_type, str) or attribute.value_type not in {"text", "number", "boolean", "choice"}:
        raise ValidationError("نوع ویژگی معتبر نیست.")
    values = attribute.choices
    if not isinstance(values, list) or len(values) > 100 or any(not isinstance(v, str) or not v.strip() or len(v) > 100 for v in values) or len(set(values)) != len(values):
        raise ValidationError("گزینه‌ها باید متن‌های غیرخالی و یکتا باشند؛ حداکثر ۱۰۰ گزینه.")
    if attribute.value_type == "choice" and not values:
        raise ValidationError("برای ویژگی انتخابی، گزینه تعریف کنید.")
    if attribute.value_type != "choice" and values:
        raise ValidationError("گزینه فقط برای نوع انتخابی مجاز است.")


def normalize_value(attribute, value):
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        raise ValidationError(f"مقدار «{attribute.name}» باید متن غیرخالی حداکثر ۲۵۵ نویسه باشد.")
    value = value.strip()
    if attribute.value_type == "number":
        try:
            number = Decimal(value.translate(DIGITS))
        except InvalidOperation as exc:
            raise ValidationError(f"«{attribute.name}» باید عدد باشد.") from exc
        if not number.is_finite() or abs(number) > Decimal('1e15') or number.as_tuple().exponent < -8:
            raise ValidationError("عدد معتبر با حداکثر ۸ رقم اعشار وارد کنید.")
        value = format(number, 'f').rstrip('0').rstrip('.') if '.' in format(number, 'f') else format(number, 'f')
        if value in {'-0', ''}:
            value = '0'
    elif attribute.value_type == "boolean":
        if value not in {"بله", "خیر"}:
            raise ValidationError(f"«{attribute.name}» فقط بله یا خیر می‌پذیرد.")
    elif attribute.value_type == "choice" and value not in attribute.choices:
        raise ValidationError(f"گزینهٔ «{attribute.name}» معتبر نیست.")
    return value


def effective_rules(category_id):
    chain, seen = [], set()
    while category_id:
        if category_id in seen:
            raise ValidationError("چرخه در دسته‌بندی‌ها وجود دارد.")
        seen.add(category_id)
        category = Category.objects.get(pk=category_id)
        chain.append(category.pk)
        category_id = category.parent_id
    rules = {}
    by_category = {}
    for rule in CategoryAttribute.objects.filter(category_id__in=chain).select_related('attribute').order_by('sort_order', 'pk'):
        by_category.setdefault(rule.category_id, []).append(rule)
    for category_id in reversed(chain):
        for rule in by_category.get(category_id, []):
            rules[rule.attribute_id] = rule
    return rules


def validate_product_specs(product, values=None, require_all=False):
    rules = effective_rules(product.category_id)
    if values is None:
        values = {row.attribute_id: row.value for row in product.attribute_values.select_related('attribute')}
    result = {}
    for ident, value in values.items():
        if ident not in rules:
            raise ValidationError("یک ویژگی برای دستهٔ اصلی یا والدهای آن مجاز نیست.")
        result[ident] = normalize_value(rules[ident].attribute, value)
    if require_all:
        missing = [rule.attribute.name for ident, rule in rules.items() if rule.required and ident not in result]
        if missing:
            raise ValidationError("ویژگی‌های اجباری تکمیل نشده‌اند: " + '، '.join(missing))
    return result


def validate_axes(axes):
    if not isinstance(axes, list) or len(axes) > 6:
        raise ValidationError("حداکثر ۶ ویژگی انتخابی برای هر محصول مجاز است.")
    seen = set()
    for axis in axes:
        if not isinstance(axis, dict) or set(axis) != {'key', 'label', 'values', 'required'}:
            raise ValidationError("ساختار ویژگی انتخابی معتبر نیست.")
        key, label, values = axis['key'], axis['label'], axis['values']
        if not isinstance(key, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', key) or key in seen:
            raise ValidationError("کلید ویژگی باید انگلیسی و یکتا باشد.")
        if not isinstance(label, str) or not label.strip() or len(label) > 80 or type(axis['required']) is not bool:
            raise ValidationError("عنوان یا وضعیت الزام ویژگی معتبر نیست.")
        if not isinstance(values, list) or not 1 <= len(values) <= 100 or any(not isinstance(v, str) or not v.strip() or len(v) > 100 for v in values) or len(set(values)) != len(values):
            raise ValidationError("گزینه‌های ویژگی باید غیرخالی و یکتا باشند؛ حداکثر ۱۰۰ گزینه.")
        seen.add(key)
    return axes


def validate_options(axes, options):
    validate_axes(axes)
    if not isinstance(options, dict) or not options:
        raise ValidationError("حداقل یک گزینه برای تنوع انتخاب کنید.")
    allowed = {axis['key']: axis for axis in axes}
    if set(options) - set(allowed):
        raise ValidationError("ویژگی ناشناخته در تنوع وجود دارد.")
    for key, value in options.items():
        if not isinstance(value, str) or value not in allowed[key]['values']:
            raise ValidationError("گزینهٔ تنوع معتبر نیست.")
    if any(axis['required'] and axis['key'] not in options for axis in axes):
        raise ValidationError("تمام ویژگی‌های اجباری تنوع را انتخاب کنید.")
    clean = {key: options[key] for key in sorted(options)}
    fingerprint = hashlib.sha256(json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return clean, fingerprint


def check_revision(product, revision):
    if type(revision) is not int or revision != product.catalog_revision:
        raise ValidationError("اطلاعات محصول تغییر کرده است؛ صفحه را تازه‌سازی کنید.")


def bump(product):
    product.catalog_revision += 1
    product.save(update_fields=['catalog_revision'])


@transaction.atomic
def save_specs(product_id, revision, values):
    with category_tree_write_lock():
        product = Product.objects.select_for_update().get(pk=product_id)
        check_revision(product, revision)
        if not isinstance(values, list) or len(values) > 100:
            raise ValidationError("فهرست مشخصات معتبر نیست.")
        submitted, seen = {}, set()
        for row in values:
            if not isinstance(row, dict) or set(row) != {'attribute_id', 'value'} or type(row['attribute_id']) is not int or row['attribute_id'] in seen:
                raise ValidationError("ساختار مشخصات نامعتبر یا تکراری است.")
            seen.add(row['attribute_id'])
            if row['value'] != '':
                submitted[row['attribute_id']] = row['value']
        clean = validate_product_specs(product, submitted, require_all=product.status == Product.Status.PUBLISHED)
        product.attribute_values.exclude(attribute_id__in=clean).delete()
        for ident, value in clean.items():
            ProductAttributeValue.objects.update_or_create(product=product, attribute_id=ident, defaults={'value': value})
        bump(product)
        return product


@transaction.atomic
def save_axes(product_id, revision, axes):
    product = Product.objects.select_for_update().get(pk=product_id)
    check_revision(product, revision)
    axes = validate_axes(axes)
    for variant in product.variants.all():
        if variant.options:
            validate_options(axes, variant.options)
    product.variant_schema = axes
    product.save(update_fields=['variant_schema'])
    bump(product)
    return product


@transaction.atomic
def save_variant(product_id, revision, payload, variant_id=None):
    product = Product.objects.select_for_update().get(pk=product_id)
    check_revision(product, revision)
    expected_fields = {'sku', 'options', 'price', 'stock', 'is_active'} | ({'expected_stock'} if variant_id else set())
    if not isinstance(payload, dict) or set(payload) != expected_fields:
        raise ValidationError("ساختار تنوع معتبر نیست.")
    for field in ['price', 'stock']:
        if type(payload[field]) is not int or payload[field] < (1 if field == 'price' else 0) or payload[field] > (9007199254740991 if field == 'price' else 2147483647):
            raise ValidationError("قیمت و موجودی باید عدد صحیح در محدودهٔ مجاز باشند.")
    if type(payload['is_active']) is not bool or not isinstance(payload['sku'], str) or not payload['sku'].strip() or len(payload['sku']) > 100:
        raise ValidationError("SKU یا وضعیت معتبر نیست.")
    options, fingerprint = validate_options(product.variant_schema, payload['options'])
    if variant_id:
        variant = ProductVariant.objects.select_for_update().get(pk=variant_id, product=product)
        if type(payload['expected_stock']) is not int or payload['expected_stock'] != variant.stock:
            raise ValidationError("موجودی از زمان بازکردن فرم تغییر کرده است؛ اطلاعات را دوباره دریافت کنید.")
    else:
        variant = ProductVariant(product=product)
    for key in ['sku', 'price', 'stock', 'is_active']:
        setattr(variant, key, payload[key].strip() if key == 'sku' else payload[key])
    variant.options, variant.combination_key = options, fingerprint
    # Keep the old fields readable for integrations throughout the transition.
    variant.color, variant.storage = (options.get('color', ''), options.get('storage', '')) if set(options) <= {'color', 'storage'} else ('', '')
    variant.full_clean(validate_unique=False, validate_constraints=False)
    variant.save()
    bump(product)
    return product
