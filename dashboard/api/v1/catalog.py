import hashlib
import json

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from dashboard.api.v1.views import OwnerAPIView, get_resource
from products.models import Attribute, Category, CategoryAttribute, Product
from products.services.attribute_service import (
    effective_rules,
    save_axes,
    save_specs,
    save_variant,
    validate_product_specs,
)
from products.services.category_service import category_tree_write_lock


def resource(request, key, pk, write=False):
    _, admin, queryset = get_resource(request, key)
    try:
        obj = queryset.get(pk=pk)
    except ObjectDoesNotExist as exc:
        raise NotFound() from exc
    allowed = (
        admin.has_change_permission(request, obj)
        if write
        else admin.has_view_permission(request, obj)
    )
    if not allowed:
        raise PermissionDenied()
    return obj


def definition(attribute):
    doc = {
        "id": attribute.pk,
        "name": attribute.name,
        "slug": attribute.slug,
        "value_type": attribute.value_type,
        "unit": attribute.unit,
        "choices": attribute.choices,
    }
    doc["revision"] = hashlib.sha256(
        json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return doc


def schema(category_id):
    return [
        {
            **definition(rule.attribute),
            "required": rule.required,
            "category_id": rule.category_id,
            "sort_order": rule.sort_order,
        }
        for rule in effective_rules(category_id).values()
    ]


def product_document(product):
    return {
        "revision": product.catalog_revision,
        "schema": schema(product.category_id),
        "values": {
            str(v.attribute_id): v.value for v in product.attribute_values.all()
        },
        "axes": product.variant_schema,
        "variants": [
            {
                "id": v.pk,
                "sku": v.sku,
                "options": v.options,
                "label": v.display_name,
                "price": v.price,
                "stock": v.stock,
                "is_active": v.is_active,
            }
            for v in product.variants.select_related("product").order_by("pk")
        ],
    }


class CatalogView(OwnerAPIView):
    http_method_names = ["get", "post", "put", "head", "options"]

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            exc = ValidationError(getattr(exc, "message_dict", None) or exc.messages)
        elif isinstance(exc, IntegrityError):
            exc = ValidationError(
                "ترکیب تنوع، SKU یا ویژگی تکراری است؛ تغییرات ذخیره نشدند."
            )
        elif isinstance(exc, ObjectDoesNotExist):
            exc = NotFound()
        return super().handle_exception(exc)


class AttributeDefinitionsView(CatalogView):
    def get(self, request, pk=None):
        if not request.user.has_perm("products.view_attribute"):
            raise PermissionDenied()
        if pk is not None:
            return Response(definition(Attribute.objects.get(pk=pk)))
        return Response([definition(a) for a in Attribute.objects.order_by("name")])

    @transaction.atomic
    def post(self, request, pk=None):
        if pk is not None:
            raise ValidationError("برای ویرایش ویژگی از PUT استفاده کنید.")
        if not request.user.has_perm("products.add_attribute"):
            raise PermissionDenied()
        data = request.data
        if not isinstance(data, dict) or set(data) != {
            "name",
            "value_type",
            "unit",
            "choices",
        }:
            raise ValidationError("ساختار ویژگی معتبر نیست.")
        from uuid import uuid4

        attribute = Attribute(slug="attr-" + uuid4().hex, **data)
        attribute.full_clean()
        attribute.save()
        return Response(definition(attribute), status=201)

    def put(self, request, pk=None):
        if pk is None:
            raise ValidationError("شناسهٔ ویژگی لازم است.")
        if not request.user.has_perm("products.change_attribute"):
            raise PermissionDenied()
        body = request.data
        if not isinstance(body, dict) or set(body) != {
            "name",
            "value_type",
            "unit",
            "choices",
            "revision",
        }:
            raise ValidationError("ساختار ویژگی معتبر نیست.")
        with category_tree_write_lock():
            attribute = Attribute.objects.select_for_update().get(pk=pk)
            if body["revision"] != definition(attribute)["revision"]:
                raise ValidationError(
                    "ویژگی تغییر کرده است؛ اطلاعات تازه را دریافت کنید."
                )
            for key in ["name", "value_type", "unit", "choices"]:
                setattr(attribute, key, body[key])
            attribute.full_clean()
            attribute.save()
            return Response(definition(attribute))


def category_document(pk):
    doc = {
        "effective": schema(pk),
        "own": list(
            CategoryAttribute.objects.filter(category_id=pk)
            .order_by("sort_order", "pk")
            .values("attribute_id", "required", "sort_order")
        ),
    }
    doc["revision"] = hashlib.sha256(
        json.dumps(doc, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    return doc


class CategorySchemaView(CatalogView):
    def get(self, request, pk):
        resource(request, "categories", pk)
        return Response(category_document(pk))

    def put(self, request, pk):
        with category_tree_write_lock():
            category = resource(request, "categories", pk, write=True)
            # Lock the category after the tree lock, consistently with category writes.
            Category.objects.select_for_update().get(pk=pk)
            body = request.data
            if (
                not isinstance(body, dict)
                or set(body) != {"revision", "rules"}
                or body["revision"] != category_document(pk)["revision"]
            ):
                raise ValidationError(
                    "ویژگی‌های دسته تغییر کرده‌اند؛ اطلاعات تازه را دریافت کنید."
                )
            if not all(
                request.user.has_perm("products." + perm + "_categoryattribute")
                for perm in ["add", "change", "delete"]
            ):
                raise PermissionDenied("مجوز مدیریت ویژگی‌های دسته ندارید.")
            rows = body["rules"]
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValidationError("حداکثر ۱۰۰ ویژگی برای دسته مجاز است.")
            ids = set()
            for row in rows:
                if (
                    not isinstance(row, dict)
                    or set(row) != {"attribute_id", "required", "sort_order"}
                    or type(row["attribute_id"]) is not int
                    or row["attribute_id"] in ids
                    or type(row["required"]) is not bool
                    or type(row["sort_order"]) is not int
                    or not 0 <= row["sort_order"] <= 10000
                ):
                    raise ValidationError("ساختار ویژگی دسته نامعتبر یا تکراری است.")
                ids.add(row["attribute_id"])
            if Attribute.objects.filter(pk__in=ids).count() != len(ids):
                raise ValidationError("ویژگی وجود ندارد.")
            CategoryAttribute.objects.filter(category=category).delete()
            CategoryAttribute.objects.bulk_create(
                [CategoryAttribute(category=category, **row) for row in rows]
            )
            # Includes descendants: removing inherited rules cannot silently invalidate products.
            for product in Product.objects.select_for_update().order_by("pk"):
                validate_product_specs(
                    product, require_all=product.status == Product.Status.PUBLISHED
                )
            return Response(category_document(pk))


class ProductCatalogView(CatalogView):
    def get(self, request, pk):
        return Response(product_document(resource(request, "products", pk)))

    def post(self, request, pk):
        with transaction.atomic():
            resource(request, "products", pk, write=True)
            data = request.data
            if not isinstance(data, dict) or set(data) != {
                "revision",
                "action",
                "data",
            }:
                raise ValidationError("ساختار درخواست معتبر نیست.")
            action = data["action"]
            if action == "specs":
                if not all(
                    request.user.has_perm("products." + perm + "_productattributevalue")
                    for perm in ["add", "change", "delete"]
                ):
                    raise PermissionDenied("مجوز مدیریت مشخصات محصول ندارید.")
                product = save_specs(pk, data["revision"], data["data"])
            elif action == "axes":
                if not request.user.has_perm("products.change_productvariant"):
                    raise PermissionDenied("مجوز مدیریت گزینه‌های تنوع ندارید.")
                product = save_axes(pk, data["revision"], data["data"])
            elif action == "variant":
                payload = data["data"]
                if not isinstance(payload, dict):
                    raise ValidationError("تنوع معتبر نیست.")
                payload = dict(payload)
                variant_id = payload.pop("id", None)
                if variant_id is not None and (
                    type(variant_id) is not int or variant_id <= 0
                ):
                    raise ValidationError("شناسهٔ تنوع معتبر نیست.")
                if variant_id is None and not request.user.has_perm(
                    "products.add_productvariant"
                ):
                    raise PermissionDenied("مجوز ساخت تنوع ندارید.")
                if variant_id is not None and not request.user.has_perm(
                    "products.change_productvariant"
                ):
                    raise PermissionDenied("مجوز ویرایش تنوع ندارید.")
                product = save_variant(pk, data["revision"], payload, variant_id)
            else:
                raise ValidationError("عملیات ناشناخته است.")
            _, model_admin, _ = get_resource(request, "products")
            model_admin.log_change(
                request, product, "Catalog configuration updated: " + action
            )
            return Response(product_document(product))
