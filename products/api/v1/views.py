from rest_framework import permissions
from rest_framework.viewsets import ReadOnlyModelViewSet

from products.services.product_service import ProductService

from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return ProductService.get_categories()


class ProductViewSet(ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return ProductService.get_active_products()
