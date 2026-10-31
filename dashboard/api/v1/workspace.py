"""HTTP adapter for the guided product workspace; no business rules in JSX."""

import hashlib
import json

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import (
    MethodNotAllowed,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response

from dashboard.api.v1.catalog import (
    CatalogView,
    definition,
    product_document,
    resource,
    schema,
)
from dashboard.api.v1.views import get_resource
from products.models import Attribute, Product
from products.services.attribute_service import effective_rules
from products.services.catalog_workflow import (
    preview_combinations,
    readiness,
    save_basic,
    save_brand,
    save_combinations,
    save_simple,
    save_specifications,
    set_publication,
)
from products.services.category_service import category_tree_write_lock
from products.services.inline_specification import (
    save_inline_specification,
    validate_request,
)

FIELDS = [
    "id",
    "name",
    "slug",
    "category_id",
    "brand_id",
    "short_description",
    "long_description_html",
    "gallery_description_html",
    "long_description",
    "gallery_description",
    "description",
    "price",
    "stock",
    "status",
    "is_active",
]


def document(item):
    result = {key: getattr(item, key) for key in FIELDS}
    result.update(product_document(item))
    result["images"] = [
        {"id": image.pk, "url": image.image.url, "is_primary": image.is_primary}
        for image in item.images.order_by("sort_order", "pk")
    ]
    result["issues"] = readiness(item)
    # Includes legacy endpoint edits and checkout stock updates, not just revision.
    result["version"] = hashlib.sha256(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in {"images", "issues"}
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return result


def permissions(user):
    return {
        name: user.has_perm("products." + name)
        for name in [
            "add_category",
            "change_category",
            "view_category",
            "add_brand",
            "change_brand",
            "view_brand",
            "add_attribute",
            "change_attribute",
            "view_attribute",
            "add_product",
            "change_product",
            "add_productvariant",
            "change_productvariant",
            "add_categoryattribute",
            "add_productattributevalue",
            "change_productattributevalue",
            "delete_productattributevalue",
        ]
    }


class WorkspaceChoicesView(CatalogView):
    http_method_names = ["get", "head", "options"]

    def get(self, request):
        caps = permissions(request.user)
        categories, brands = [], []
        if caps["view_category"]:
            _, _, rows = get_resource(request, "categories")
            categories = list(
                rows.values("id", "name", "parent_id", "slug", "sort_order")
            )
        if caps["view_brand"]:
            _, _, rows = get_resource(request, "brands")
            brands = list(rows.values("id", "name", "slug"))
        return Response(
            {
                "categories": categories,
                "brands": brands,
                "attributes": [
                    definition(a) for a in Attribute.objects.order_by("name")
                ]
                if caps["view_attribute"]
                else [],
                "permissions": caps,
                "max_combinations": 200,
            }
        )


class WorkspaceProductView(CatalogView):
    http_method_names = ["get", "post", "head", "options"]

    def get(self, request, pk=None):
        if pk is None:
            raise MethodNotAllowed("GET")
        return Response(document(resource(request, "products", pk)))

    def post(self, request, pk=None):
        body = request.data
        if pk is None:
            if not isinstance(body, dict) or set(body) != {"basic"}:
                raise ValidationError("اطلاعات اولیهٔ محصول معتبر نیست.")
            _, admin, _ = get_resource(request, "products")
            if not admin.has_add_permission(request):
                raise PermissionDenied()
            with transaction.atomic():
                validate_references(request, body["basic"])
                item = save_basic(body["basic"])
                admin.log_addition(
                    request, item, "Created through guided catalog workspace."
                )
                return Response(document(item), status=201)
        if not isinstance(body, dict) or set(body) != {"version", "action", "data"}:
            raise ValidationError("ساختار درخواست معتبر نیست.")
        with category_tree_write_lock():
            resource(request, "products", pk, write=True)
            item = Product.objects.select_for_update().get(pk=pk)
            if body["version"] != document(item)["version"]:
                raise ValidationError(
                    "اطلاعات یا موجودی تغییر کرده است؛ دریافت اطلاعات تازه را بزنید. تغییرات قدیمی ذخیره نشدند."
                )
            action, data = body["action"], body["data"]
            if action == "basic":
                validate_references(request, data)
                item = save_basic(data, pk, item.catalog_revision)
            elif action == "specs":
                require(
                    request,
                    [
                        "add_productattributevalue",
                        "change_productattributevalue",
                        "delete_productattributevalue",
                    ],
                )
                item = save_specifications(pk, item.catalog_revision, data)
            elif action == "inline-specification":
                validate_request(data)
                require(
                    request,
                    [
                        "add_productattributevalue",
                        "change_productattributevalue",
                        "delete_productattributevalue",
                    ],
                )
                if "definition" in data:
                    require(request, ["add_attribute"])
                else:
                    require(request, ["view_attribute"])
                if "definition" in data or data["attribute_id"] not in effective_rules(
                    item.category_id
                ):
                    resource(request, "categories", item.category_id, write=True)
                    require(request, ["add_categoryattribute"])
                item, attribute, created, linked = save_inline_specification(
                    pk, item.catalog_revision, data
                )
                if created:
                    _, attribute_admin, _ = get_resource(request, "attributes")
                    attribute_admin.log_addition(
                        request, attribute, "Created inside product specifications."
                    )
                if linked:
                    _, category_admin, _ = get_resource(request, "categories")
                    category_admin.log_change(
                        request,
                        item.category,
                        "Optional specification added: " + attribute.name,
                    )
            elif action == "combinations":
                if (
                    not isinstance(data, dict)
                    or set(data) != {"axes", "rows"}
                    or not isinstance(data["rows"], list)
                ):
                    raise ValidationError("ساختار جدول تنوع معتبر نیست.")
                # All rows are checked before any operation; atomic service handles rollback.
                require(request, ["change_productvariant"])
                if any(
                    isinstance(row, dict) and row.get("id") is None
                    for row in data["rows"]
                ):
                    require(request, ["add_productvariant"])
                item = save_combinations(
                    pk, item.catalog_revision, data["axes"], data["rows"]
                )
            elif action == "simple":
                item = save_simple(pk, item.catalog_revision, data)
            elif action == "publication":
                item = set_publication(pk, item.catalog_revision, data)
            else:
                raise ValidationError("عملیات ناشناخته است.")
            _, admin, _ = get_resource(request, "products")
            admin.log_change(request, item, "Guided catalog workspace: " + action)
            return Response(document(item))


def require(request, names):
    if not all(request.user.has_perm("products." + name) for name in names):
        raise PermissionDenied(
            "مجوز تغییر این بخش را ندارید؛ دسترسی‌های کاربر مدیریت را بررسی کنید."
        )


class CombinationPreviewView(CatalogView):
    http_method_names = ["post", "options"]

    def post(self, request):
        require(request, ["change_product", "add_productvariant"])
        if not isinstance(request.data, dict) or set(request.data) != {"axes"}:
            raise ValidationError("گزینه‌ها معتبر نیستند.")
        return Response({"rows": preview_combinations(request.data["axes"])})


class CategorySpecificationView(CatalogView):
    http_method_names = ["get", "head", "options"]

    def get(self, request, pk):
        resource(request, "categories", pk)
        return Response(schema(pk))


class WorkspaceBrandView(CatalogView):
    http_method_names = ["post", "put", "options"]

    @transaction.atomic
    def post(self, request, pk=None):
        if pk is not None:
            raise MethodNotAllowed("POST")
        _, admin, _ = get_resource(request, "brands")
        if not admin.has_add_permission(request):
            raise PermissionDenied()
        brand = save_brand(request.data)
        admin.log_addition(request, brand, "Created through catalog workspace.")
        return Response(
            {"id": brand.pk, "name": brand.name, "slug": brand.slug}, status=201
        )

    @transaction.atomic
    def put(self, request, pk=None):
        if pk is None:
            raise MethodNotAllowed("PUT")
        _, admin, rows = get_resource(request, "brands")
        brand = get_object_or_404(rows, pk=pk)
        if not admin.has_change_permission(request, brand):
            raise PermissionDenied()
        brand = save_brand(request.data, pk)
        admin.log_change(request, brand, "Updated through catalog workspace.")
        return Response({"id": brand.pk, "name": brand.name, "slug": brand.slug})


def validate_references(request, data):
    if not isinstance(data, dict):
        raise ValidationError("اطلاعات محصول معتبر نیست.")
    for field, name in [("category_id", "categories"), ("brand_id", "brands")]:
        if field in data and data[field] is not None:
            value = data[field]
            if type(value) is not int or value <= 0:
                raise ValidationError({field: "انتخاب معتبر انجام دهید."})
            _, _, rows = get_resource(request, name)
            get_object_or_404(rows, pk=value)
