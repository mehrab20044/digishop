from django import forms
from django.db import IntegrityError, transaction
from rest_framework.exceptions import (
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response

from products.models import Product

from .dashboard_api import (
    OwnerAPIView,
    detail_data,
    get_resource,
)


class ProductCreateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "category",
            "brand",
            "price",
            "stock",
            "short_description",
            "long_description",
            "gallery_description",
        ]


class ProductCreateView(OwnerAPIView):
    http_method_names = ["post", "options"]

    def post(self, request):
        _, model_admin, _ = get_resource(
            request,
            "products",
        )

        if not model_admin.has_add_permission(request):
            raise PermissionDenied(
                "اجازهٔ افزودن محصول ندارید."
            )

        if not isinstance(request.data, dict):
            raise ValidationError(
                "بدنهٔ درخواست باید یک شیء JSON باشد."
            )

        allowed = set(ProductCreateForm.base_fields)
        unknown = set(request.data) - allowed

        if unknown:
            raise ValidationError({
                "detail": (
                    "فیلد غیرمجاز: "
                    + ", ".join(sorted(unknown))
                ),
            })

        form = ProductCreateForm(
            data=request.data,
            instance=Product(
                status=Product.Status.DRAFT,
                is_active=False,
            ),
        )

        if not form.is_valid():
            raise ValidationError({
                field: list(errors)
                for field, errors in form.errors.items()
            })

        try:
            with transaction.atomic():
                product = form.save()

                model_admin.log_addition(
                    request,
                    product,
                    "Created through owner dashboard.",
                )

                data = detail_data("products", product)

        except IntegrityError as exc:
            raise ValidationError({
                "detail": (
                    "ذخیره انجام نشد؛ نامک تکراری یا "
                    "تغییر هم‌زمان دسته‌بندی و برند را بررسی کنید."
                ),
            }) from exc

        return Response(data, status=201)