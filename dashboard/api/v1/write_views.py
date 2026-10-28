from django import forms
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from dashboard.api.v1.views import (
    OwnerAPIView,
    detail_data,
    get_resource,
)
from products.services.category_service import (
    category_tree_write_lock,
    save_category,
)

EDIT_FIELDS = {
    "products": [
        "name",
        "slug",
        "price",
        "stock",
        "short_description",
        "long_description",
        "gallery_description",
        "status",
        "is_active",
    ],
    "categories": [
        "name",
        "slug",
        "description",
        "sort_order",
        "parent_id",
        "related_category_ids",
    ],
    "brands": ["name", "slug"],
    "attributes": ["name", "slug"],
}

CREATABLE = {"categories", "brands", "attributes"}


def validate_payload(resource, payload):
    fields = EDIT_FIELDS.get(resource)

    if fields is None:
        raise PermissionDenied(
            "ویرایش این بخش هنوز فعال نشده است."
        )

    if not isinstance(payload, dict):
        raise ValidationError(
            "بدنهٔ درخواست باید یک شیء JSON باشد."
        )

    unknown = set(payload) - set(fields)

    if unknown:
        raise ValidationError({
            "detail": "فیلد غیرمجاز: " + ", ".join(sorted(unknown)),
        })

    if not payload:
        raise ValidationError("اطلاعاتی برای ذخیره ارسال نشده.")

    return fields


def log_saved_record(request, model_admin, saved, *, created, fields):
    if created:
        model_admin.log_addition(
            request,
            saved,
            "Created through owner dashboard.",
        )
    else:
        model_admin.log_change(
            request,
            saved,
            "Updated through owner dashboard: "
            + ", ".join(fields),
        )


def save_category_record(request, pk=None):
    # Acquire before reading the category or validating its new parent.
    with category_tree_write_lock():
        _, model_admin, queryset = get_resource(
            request,
            "categories",
        )

        if pk is None:
            if not model_admin.has_add_permission(request):
                raise PermissionDenied(
                    "اجازهٔ افزودن دسته‌بندی ندارید."
                )
        else:
            instance = get_object_or_404(
                queryset.select_related(None).select_for_update(),
                pk=pk,
            )

            if not model_admin.has_change_permission(
                request,
                instance,
            ):
                raise PermissionDenied(
                    "اجازهٔ ویرایش این دسته‌بندی را ندارید."
                )

        saved = save_category(
            category_id=pk,
            data=dict(request.data),
        )

        log_saved_record(
            request,
            model_admin,
            saved,
            created=pk is None,
            fields=sorted(request.data),
        )

        return detail_data("categories", saved)


@transaction.atomic
def save_record(request, resource, pk=None):
    fields = validate_payload(resource, request.data)

    if resource == "categories":
        return save_category_record(request, pk)

    config, model_admin, queryset = get_resource(
        request,
        resource,
    )

    if pk is None:
        if resource not in CREATABLE:
            raise PermissionDenied(
                "ایجاد رکورد در این بخش هنوز فعال نیست."
            )

        if not model_admin.has_add_permission(request):
            raise PermissionDenied(
                "اجازهٔ افزودن ندارید."
            )

        instance = None
        data = dict(request.data)
    else:
        instance = get_object_or_404(
            queryset.select_related(None).select_for_update(),
            pk=pk,
        )

        if not model_admin.has_change_permission(
            request,
            instance,
        ):
            raise PermissionDenied(
                "اجازهٔ ویرایش این رکورد را ندارید."
            )

        data = {
            field: getattr(instance, field)
            for field in fields
        }
        data.update(request.data)

    Form = forms.modelform_factory(
        config["model"],
        fields=fields,
    )
    form = Form(data=data, instance=instance)

    if not form.is_valid():
        raise ValidationError({
            field: list(errors)
            for field, errors in form.errors.items()
        })

    product = form.instance

    if resource == "products":
        if (
            product.status == product.Status.PUBLISHED
            and product.variants.filter(price=0).exists()
        ):
            raise ValidationError({
                "status": [
                    "قیمت تمام تنوع‌ها باید بیشتر از صفر باشد."
                ],
            })

        if (
            product.is_active
            and not product.images.filter(
                is_primary=True,
            ).exists()
        ):
            raise ValidationError({
                "is_active": [
                    "ابتدا تصویر اصلی را در Django Admin تعیین کنید."
                ],
            })

    saved = form.save()

    log_saved_record(
        request,
        model_admin,
        saved,
        created=pk is None,
        fields=form.changed_data,
    )

    return detail_data(resource, saved)


def write_response(request, resource, pk=None):
    try:
        data = save_record(request, resource, pk)
    except IntegrityError as exc:
        raise ValidationError({
            "detail": (
                "ذخیره به دلیل تداخل داده‌ها انجام نشد؛ "
                "نام و نامک را بررسی و دوباره تلاش کنید."
            ),
        }) from exc

    return Response(data, status=201 if pk is None else 200)


class OwnerCSRFView(OwnerAPIView):
    def get(self, request):
        return Response({
            "csrfToken": get_token(request),
        })


class DashboardCreateView(OwnerAPIView):
    http_method_names = ["post", "options"]

    def post(self, request, resource):
        return write_response(request, resource)


class DashboardUpdateView(OwnerAPIView):
    http_method_names = ["patch", "options"]

    def patch(self, request, resource, pk):
        return write_response(request, resource, pk)