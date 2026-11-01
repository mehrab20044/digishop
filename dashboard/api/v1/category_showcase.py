from dashboard.api.v1.views import OwnerAPIView, detail_data, get_resource
from django.db import transaction
from django.shortcuts import get_object_or_404
from products.services.category_showcase_service import (
    home_category_ids,
    replace_category_image,
    set_home_categories,
)
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response


class HomeCategoriesView(OwnerAPIView):
    http_method_names = ["get", "put", "head", "options"]

    def get(self, request):
        get_resource(request, "categories")
        return Response({"category_ids": home_category_ids()})

    @transaction.atomic
    def put(self, request):
        _, model_admin, _ = get_resource(request, "categories")
        if not model_admin.has_change_permission(request):
            raise PermissionDenied("اجازه تغییر دسته‌بندی‌ها را ندارید.")
        if not isinstance(request.data, dict) or set(request.data) != {
            "category_ids",
            "expected_ids",
        }:
            raise ValidationError("شناسه‌های انتخاب‌شده و نسخه قبلی را ارسال کنید.")
        ids = set_home_categories(
            request.data["category_ids"], request.data["expected_ids"]
        )
        # Audit the category changes, using the existing category permissions.
        from products.models import Category

        for category in Category.objects.filter(pk__in=ids):
            model_admin.log_change(
                request, category, "Updated the five homepage category positions."
            )
        return Response({"category_ids": ids})


class CategoryImageView(OwnerAPIView):
    http_method_names = ["put", "delete", "options"]
    parser_classes = [MultiPartParser]

    def write(self, request, pk, upload):
        _, model_admin, queryset = get_resource(request, "categories")
        category = get_object_or_404(queryset, pk=pk)
        if not model_admin.has_change_permission(request, category):
            raise PermissionDenied("اجازه تغییر عکس این دسته را ندارید.")
        category = replace_category_image(
            category_id=pk,
            upload=upload,
            audit=lambda obj: model_admin.log_change(
                request, obj, "Changed category image through dashboard."
            ),
        )
        return Response(detail_data("categories", category))

    def put(self, request, pk):
        if set(request.data) != {"image"} or "image" not in request.FILES:
            raise ValidationError({"image": "یک فایل تصویر ارسال کنید."})
        return self.write(request, pk, request.FILES["image"])

    def delete(self, request, pk):
        return self.write(request, pk, None)
