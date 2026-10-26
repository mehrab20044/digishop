from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.authentication import SessionJWTAuthentication
from accounts.models import Address
from accounts.services.profile_service import get_profile_status
from accounts.services.staff_service import can_manage
from dashboard.permissions import IsManagementSession
from products.models import (
    Attribute,
    Brand,
    Category,
    Product,
)
from seo.models import SEOSettings

User = get_user_model()





class DashboardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = None


# Only explicitly approved models and fields are exposed.
# Passwords, OTP records and authentication tokens are never serialized.
RESOURCES = {
    "products": {
        "model": Product,
        "label": "محصولات",
        "columns": [
            ["id", "شناسه"],
            ["name", "نام محصول"],
            ["category", "دسته‌بندی"],
            ["brand", "برند"],
            ["price", "قیمت ثبت‌شده"],
            ["stock", "موجودی پایه"],
            ["status", "انتشار"],
            ["is_active", "فعال"],
        ],
    },
    "categories": {
        "model": Category,
        "label": "دسته‌بندی‌ها",
        "columns": [
            ["id", "شناسه"],
            ["name", "نام"],
            ["slug", "نامک"],
        ],
    },
    "brands": {
        "model": Brand,
        "label": "برندها",
        "columns": [
            ["id", "شناسه"],
            ["name", "نام"],
            ["slug", "نامک"],
        ],
    },
    "attributes": {
        "model": Attribute,
        "label": "ویژگی‌ها",
        "columns": [
            ["id", "شناسه"],
            ["name", "نام"],
            ["slug", "نامک"],
        ],
    },
    "users": {
        "model": User,
        "label": "کاربران",
        "columns": [
            ["id", "شناسه"],
            ["full_name", "نام کامل"],
            ["phone", "موبایل"],
            ["is_active", "فعال"],
            ["is_staff", "عضو مدیریت"],
        ],
    },
    "addresses": {
        "model": Address,
        "label": "آدرس‌ها",
        "columns": [
            ["id", "شناسه"],
            ["user", "کاربر"],
            ["recipient_name", "گیرنده"],
            ["city", "شهر"],
            ["is_default", "پیش‌فرض"],
        ],
    },
    "groups": {
        "model": Group,
        "label": "گروه‌های کاربری",
        "columns": [
            ["id", "شناسه"],
            ["name", "نام گروه"],
        ],
    },
}


def file_url(field):
    return field.url if field else None


def pick(instance, fields):
    return {
        field: getattr(instance, field)
        for field in fields
    }


def address_data(address):
    return {
        **pick(
            address,
            [
                "id",
                "recipient_name",
                "recipient_phone",
                "province",
                "city",
                "street_address",
                "building_number",
                "unit",
                "postal_code",
                "is_default",
                "created_at",
                "updated_at",
            ],
        ),
        "user_id": address.user_id,
        "user": address.user.phone,
    }


def user_phone(user):
    return user.phone


def summary_data(resource, obj):
    if resource == "products":
        return {
            **pick(
                obj,
                ["id", "name", "price", "stock", "is_active"],
            ),
            "category": obj.category.name,
            "brand": obj.brand.name if obj.brand else None,
            "status": obj.get_status_display(),
        }

    if resource == "users":
        return {
            **pick(
                obj,
                ["id", "phone", "is_active", "is_staff"],
            ),
            "full_name": obj.get_full_name(),
            "phone": user_phone(obj),
        }

    if resource == "addresses":
        return {
            **pick(
                obj,
                ["id", "recipient_name", "city", "is_default"],
            ),
            "user": obj.user.phone,
        }

    fields = ["id", "name"]

    if resource != "groups":
        fields.append("slug")

    return pick(obj, fields)


def detail_data(resource, obj):
    data = summary_data(resource, obj)

    if resource == "products":
        data.update(
            pick(
                obj,
                [
                    "slug",
                    "short_description",
                    "long_description",
                    "gallery_description",
                    "created_at",
                ],
            ),
        )

        data["category_id"] = obj.category_id
        data["brand_id"] = obj.brand_id

        # Include inactive variants as well, unlike the public API.
        data["variants"] = [
            pick(
                variant,
                [
                    "id",
                    "sku",
                    "color",
                    "storage",
                    "price",
                    "stock",
                    "is_active",
                ],
            )
            for variant in obj.variants.all()
        ]

        data["attribute_values"] = [
            {
                "id": value.pk,
                "attribute": value.attribute.name,
                "value": value.value,
            }
            for value in obj.attribute_values.all()
        ]

        data["images"] = [
            {
                "id": image.pk,
                "image": file_url(image.image),
                "sort_order": image.sort_order,
                "is_primary": image.is_primary,
            }
            for image in obj.images.all()
        ]

    elif resource == "categories":
        data["allowed_attributes"] = [
            {
                "id": relation.attribute_id,
                "name": relation.attribute.name,
            }
            for relation in obj.category_attributes.all()
        ]

    elif resource == "users":
        data.update(
            pick(
                obj,
                [
                    "first_name",
                    "last_name",
                    "email",
                    "is_superuser",
                    "date_joined",
                    "last_login",
                ],
            ),
        )

        profile = getattr(obj, "profile", None)

        data["phone_verified_at"] = obj.phone_verified_at

        data["profile"] = (
            {
                "image": file_url(profile.image),
                "description": profile.description,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            }
            if profile
            else None
        )

        data["profile_status"] = get_profile_status(obj)
        data["addresses"] = [
            address_data(address)
            for address in obj.addresses.all()
        ]
        data["groups"] = [
            {"id": group.pk, "name": group.name}
            for group in obj.groups.all()
        ]
        data["user_permissions"] = [
            {
                "name": permission.name,
                "codename": (
                    f"{permission.content_type.app_label}."
                    f"{permission.codename}"
                ),
            }
            for permission in obj.user_permissions.all()
        ]

    elif resource == "addresses":
        data = address_data(obj)

    elif resource == "groups":
        data["permissions"] = [
            {
                "name": permission.name,
                "codename": (
                    f"{permission.content_type.app_label}."
                    f"{permission.codename}"
                ),
            }
            for permission in obj.permissions.all()
        ]

    return data


def get_resource(request, resource):
    if (
        resource in {"users", "groups", "addresses"}
        and not request.user.is_superuser
    ):
        raise PermissionDenied(
            "مدیریت این بخش فعلاً فقط برای صاحب سایت مجاز است."
        )

    config = RESOURCES.get(resource)

    if config is None:
        raise NotFound("بخش موردنظر وجود ندارد.")

    model_admin = admin.site.get_model_admin(config["model"])

    if not model_admin.has_view_permission(request):
        raise PermissionDenied("اجازهٔ مشاهدهٔ این بخش را ندارید.")

    queryset = model_admin.get_queryset(request)

    if resource == "products":
        queryset = queryset.select_related(
            "category",
            "brand",
        ).prefetch_related(
            "variants",
            "images",
            "attribute_values__attribute",
        )

    elif resource == "categories":
        queryset = queryset.prefetch_related(
            "category_attributes__attribute",
        )

    elif resource == "users":
        queryset = queryset.select_related(
            "profile",
        ).prefetch_related(
            "addresses__user",
            "groups",
            "user_permissions__content_type",
        )

    elif resource == "addresses":
        queryset = queryset.select_related("user")

    elif resource == "groups":
        queryset = queryset.prefetch_related(
            "permissions__content_type",
        )

    # Keep pagination deterministic.
    return config, model_admin, queryset.order_by("-pk")


@method_decorator(never_cache, name="dispatch")
class OwnerAPIView(APIView):
    authentication_classes = [SessionJWTAuthentication]
    permission_classes = [IsManagementSession]
    http_method_names = ["get", "head", "options"]



class DashboardIndexView(OwnerAPIView):
    def get(self, request):
        resources = []
        user = request.user

        creatable = {"products", "categories", "brands", "attributes"}
        editable = {"products", "categories", "brands", "attributes"}

        for key, config in RESOURCES.items():
            if key == "addresses":
                continue

            if key in {"users", "groups"} and not user.is_superuser:
                continue

            if not admin.site.is_registered(config["model"]):
                continue

            model_admin = admin.site.get_model_admin(config["model"])

            if not model_admin.has_view_permission(request):
                continue

            resources.append({
                "key": key,
                "label": config["label"],
                "columns": config["columns"],
                "count": model_admin.get_queryset(request).count(),
                "capabilities": {
                    "view": True,
                    "add": (
                        key in creatable
                        and model_admin.has_add_permission(request)
                    ),
                    "change": (
                        key in editable
                        and model_admin.has_change_permission(request)
                    ),
                    "delete": False,
                },
            })

        seo_permissions = (
            "seo.view_seosettings",
            "seo.change_seosettings",
            "seo.view_seosettingslog",
        )

        if any(user.has_perm(item) for item in seo_permissions):
            resources.append({
                "key": "seo",
                "label": "مدیریت SEO",
                "columns": [],
                "count": SEOSettings.objects.count(),
                "capabilities": {
                    "view": True,
                    "add": False,
                    "change": user.has_perm("seo.change_seosettings"),
                    "delete": False,
                },
            })

        if can_manage(user, "view"):
            resources.append({
                "key": "staff",
                "label": "همکاران",
                "columns": [],
                "count": User.objects.filter(is_staff=True).count(),
                "capabilities": {
                    "view": True,
                    "add": can_manage(user, "add"),
                    "change": can_manage(user, "change"),
                    "delete": False,
                },
            })

        return Response({
            "user": {
                "phone": user.phone,
                "username": user.phone,
                "full_name": user.get_full_name(),
            },
            "resources": resources,
        })



class DashboardListView(OwnerAPIView):
    def get(self, request, resource):
        if (
            resource not in RESOURCES
            or not admin.site.is_registered(
                RESOURCES[resource]["model"],
            )
        ):
            raise NotFound("این بخش در پنل فعال نیست.")

        config, model_admin, queryset = get_resource(
            request,
            resource,
        )

        search = request.query_params.get("search", "").strip()

        if len(search) > 150:
            raise serializers.ValidationError({
                "search": "جست‌وجو حداکثر ۱۵۰ کاراکتر باشد.",
            })

        if search:
            queryset, use_distinct = model_admin.get_search_results(
                request,
                queryset,
                search,
            )

            if use_distinct:
                queryset = queryset.distinct()

        paginator = DashboardPagination()
        page = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )

        return paginator.get_paginated_response([
            summary_data(resource, obj)
            for obj in page
        ])


class DashboardDetailView(OwnerAPIView):
    def get(self, request, resource, pk):
        if (
            resource not in RESOURCES
            or not admin.site.is_registered(
                RESOURCES[resource]["model"],
            )
        ):
            raise NotFound("این بخش در پنل فعال نیست.")

        _, model_admin, queryset = get_resource(
            request,
            resource,
        )

        obj = get_object_or_404(queryset, pk=pk)

        if not model_admin.has_view_permission(request, obj):
            raise PermissionDenied(
                "اجازهٔ مشاهدهٔ این رکورد را ندارید.",
            )

        return Response(detail_data(resource, obj))