import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import FileExtensionValidator
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from dashboard.api.v1.views import OwnerAPIView, get_resource
from products.models import ProductImage
from products.services.image_service import prepare_product_image
from products.validators import (
    validate_product_image_content,
    validate_product_image_size,
)

logger = logging.getLogger(__name__)

validate_extension = FileExtensionValidator(
    allowed_extensions=["jpg", "jpeg", "png", "webp"],
)


class GalleryUploadSerializer(serializers.Serializer):
    images = serializers.ListField(
        child=serializers.FileField(),
        min_length=1,
        max_length=10,
    )

    def validate_images(self, files):
        errors = {}

        for index, image in enumerate(files):
            try:
                validate_product_image_size(image)
                validate_extension(image)
                validate_product_image_content(image)
            except DjangoValidationError as exc:
                errors[str(index + 1)] = exc.messages

        if errors:
            raise serializers.ValidationError(errors)

        return files


class GalleryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = [
            "id",
            "image",
            "sort_order",
            "is_primary",
        ]
        read_only_fields = fields


def gallery_data(product):
    images = product.images.order_by("sort_order", "id")

    return {
        "images": GalleryImageSerializer(
            images,
            many=True,
        ).data,
    }


class ProductGalleryView(OwnerAPIView):
    http_method_names = ["get", "post", "head", "options"]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, pk):
        _, _, queryset = get_resource(request, "products")
        product = get_object_or_404(queryset, pk=pk)

        return Response(gallery_data(product))

    def post(self, request, pk):
        _, model_admin, queryset = get_resource(
            request,
            "products",
        )

        product = get_object_or_404(queryset, pk=pk)

        if not model_admin.has_change_permission(request, product):
            raise PermissionDenied(
                "اجازهٔ تغییر تصاویر این محصول را ندارید."
            )

        serializer = GalleryUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Validate all files before processing or saving any of them.
        try:
            prepared = [
                prepare_product_image(image)
                for image in serializer.validated_data["images"]
            ]
        except (OSError, SyntaxError, ValueError) as exc:
            raise serializers.ValidationError({
                "images": "پردازش یکی از تصاویر ممکن نیست.",
            }) from exc

        stored_files = []

        try:
            with transaction.atomic():
                # Lock only the product row, without joined tables.
                product = get_object_or_404(
                    queryset.select_related(None).select_for_update(),
                    pk=pk,
                )

                if not model_admin.has_change_permission(
                    request,
                    product,
                ):
                    raise PermissionDenied(
                        "اجازهٔ تغییر تصاویر این محصول را ندارید."
                    )

                max_order = (
                    product.images.aggregate(
                        value=Max("sort_order"),
                    )["value"]
                    or 0
                )

                has_primary = product.images.filter(
                    is_primary=True,
                ).exists()

                for offset, image in enumerate(prepared, start=1):
                    record = ProductImage(
                        product=product,
                        sort_order=max_order + offset,
                        is_primary=not has_primary and offset == 1,
                    )

                    record.image.save(
                        image.name,
                        image,
                        save=False,
                    )

                    stored_files.append((
                        record.image.storage,
                        record.image.name,
                    ))

                    record.save()

                model_admin.log_change(
                    request,
                    product,
                    f"Added {len(prepared)} gallery images through dashboard.",
                )

                result = gallery_data(product)

        except Exception as exc:
            # A database rollback does not remove uploaded storage files.
            for storage, name in stored_files:
                try:
                    storage.delete(name)
                except Exception:
                    logger.exception(
                        "Failed to clean up a gallery upload."
                    )

            if isinstance(exc, IntegrityError):
                raise serializers.ValidationError({
                    "images": (
                        "تداخل در ذخیرهٔ تصاویر؛ "
                        "گالری را تازه‌سازی و دوباره تلاش کنید."
                    ),
                }) from exc

            raise

        return Response(result, status=201)