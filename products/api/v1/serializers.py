from rest_framework import serializers

from products.models import (
    Brand,
    Category,
    Product,
    ProductAttributeValue,
    ProductImage,
    ProductVariant,
)
from products.services.variant_service import (
    get_default_variant,
    is_product_available,
)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = [
            "id",
            "image",
            "title",
            "alt_text",
            "description",
            "caption",
            "sort_order",
            "is_primary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields



class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["id", "name", "slug"]


class ProductAttributeValueSerializer(serializers.ModelSerializer):
    unit = serializers.CharField(source="attribute.unit", read_only=True)
    attribute = serializers.CharField(
        source="attribute.name",
        read_only=True,
    )

    class Meta:
        model = ProductAttributeValue
        fields = ["id", "attribute", "value", "unit"]



class ProductVariantSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="display_name", read_only=True)
    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "options",
            "label",
            "color",
            "storage",
            "price",
            "stock",
            "is_active",
        ]
        read_only_fields = fields



class ProductSerializer(serializers.ModelSerializer):
    long_description_html = serializers.SerializerMethodField()
    gallery_description_html = serializers.SerializerMethodField()

    def get_long_description_html(self, obj):
        from products.services.richtext_service import sanitize_richtext
        return sanitize_richtext(obj.long_description_html)

    def get_gallery_description_html(self, obj):
        from products.services.richtext_service import sanitize_richtext
        return sanitize_richtext(obj.gallery_description_html)

    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    brand = BrandSerializer(read_only=True)
    attribute_values = ProductAttributeValueSerializer(
        many=True,
        read_only=True,
)
    variants = serializers.SerializerMethodField()
    default_variant = serializers.SerializerMethodField()
    is_available = serializers.SerializerMethodField()
    effective_price = serializers.IntegerField(
        source="_effective_price",
        read_only=True,
        allow_null=True,
    )
    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "name",
            "slug",
            "description",
            "short_description",
            "long_description",
            "gallery_description",
            "long_description_html",
            "gallery_description_html",
            "price",
            "stock",
            "image",
            "images",
            "is_active",
            "created_at",
            "brand",
            "attribute_values",
            "variants",
            "variant_schema",
            "default_variant",
            "is_available",
            "effective_price",
        ]
    def get_default_variant(self, obj):
        variant = get_default_variant(obj)

        if variant is None:
            return None

        return ProductVariantSerializer(variant).data
    def get_is_available(self, obj):
        return is_product_available(obj)

    def get_variants(self, obj):
        variants = obj.variants.filter(is_active=True).select_related("product").order_by("price", "id")
        return ProductVariantSerializer(variants, many=True).data