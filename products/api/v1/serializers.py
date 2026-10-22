from rest_framework import serializers

from products.models import Category, Product

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields =["id","name","slug"]


class ProductSerializer(serializers.ModelSerializer):
    category =CategorySerializer(read_only = True)

    class Meta:
        model = Product
        fields =[
            "id",
            "category",
            "name",
            "slug",
            "description",
            "price",
            "stock",
            "image",
            "is_active",
            "created_at"
        ]