from rest_framework import serializers

from products.models import (
    Brand,
    Category,
    Product,
    ProductAttributeValue,
    ProductImage,
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
    attribute = serializers.CharField(
        source="attribute.name",
        read_only=True,
    )

    class Meta:
        model = ProductAttributeValue
        fields = ["id", "attribute", "value"]


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    brand = BrandSerializer(read_only=True)
    attribute_values = ProductAttributeValueSerializer(
        many=True,
        read_only=True,
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
            "price",
            "stock",
            "image",
            "images",
            "is_active",
            "created_at",
            "brand",
            "attribute_values",
        ]
