"""Create/reuse a specification and apply it without leaving the product editor."""

from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction

from products.models import Attribute, CategoryAttribute, Product
from products.services.attribute_service import (
    check_revision,
    effective_rules,
    save_specs,
)
from products.services.category_service import category_tree_write_lock


def validate_request(data):
    if not isinstance(data, dict):
        raise ValidationError("ساختار مشخصه معتبر نیست.")
    selectors = {"attribute_id", "definition"} & set(data)
    if len(selectors) != 1 or set(data) != selectors | {"value", "values"}:
        raise ValidationError("یک ویژگی موجود یا تعریف ویژگی جدید را ارسال کنید.")
    if (
        not isinstance(data["values"], list)
        or not isinstance(data["value"], str)
        or not data["value"].strip()
    ):
        raise ValidationError("مقدار و فهرست مشخصات معتبر نیست.")
    if "attribute_id" in data and (
        type(data["attribute_id"]) is not int or data["attribute_id"] <= 0
    ):
        raise ValidationError("ویژگی معتبر انتخاب کنید.")
    if "definition" in data:
        definition = data["definition"]
        if not isinstance(definition, dict) or set(definition) != {
            "name",
            "value_type",
            "unit",
            "choices",
        }:
            raise ValidationError("تعریف ویژگی معتبر نیست.")
    return data


def save_inline_specification(product_id, revision, data):
    data = validate_request(data)
    with category_tree_write_lock(), transaction.atomic():
        item = Product.objects.select_for_update().get(pk=product_id)
        check_revision(item, revision)
        created = "definition" in data
        if created:
            attribute = Attribute(slug="attr-" + uuid4().hex, **data["definition"])
            attribute.full_clean()
            attribute.save()
        else:
            attribute = Attribute.objects.get(pk=data["attribute_id"])
        linked = False
        if attribute.pk not in effective_rules(item.category_id):
            CategoryAttribute.objects.create(
                category_id=item.category_id, attribute=attribute, required=False
            )
            linked = True
        # Existing edits in this form are saved in the same transaction, not discarded.
        values = list(data["values"])
        if any(
            not isinstance(row, dict) or row.get("attribute_id") == attribute.pk
            for row in values
        ):
            raise ValidationError(
                "ویژگی انتخاب‌شده قبلاً در این فرم است؛ مقدارش را در فهرست ویرایش کنید."
            )
        values.append({"attribute_id": attribute.pk, "value": data["value"]})
        item = save_specs(item.pk, item.catalog_revision, values)
        return item, attribute, created, linked
