from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from products.filters import ProductFilter
from products.services.category_query_service import public_category_tree
from products.services.product_service import ProductService

from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(ReadOnlyModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return ProductService.get_categories()

    @action(
        detail=False,
        methods=["get"],
        pagination_class=None,
    )
    def tree(self, request):
        return Response(public_category_tree())



class ProductOrderingFilter(OrderingFilter):
    def get_ordering(self, request, queryset, view):
        ordering = super().get_ordering(request, queryset, view)

        if not ordering:
            return ordering

        return [
            item.replace("effective_price", "_effective_price")
            if item.lstrip("-") == "effective_price"
            else item
            for item in ordering
        ]


class ProductViewSet(ReadOnlyModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]

    filter_backends = [
    DjangoFilterBackend,
    SearchFilter,
    ProductOrderingFilter,
]
    filterset_class = ProductFilter
    search_fields = ["name", "description"]

    ordering_fields = ["effective_price", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = ProductService.get_active_products()
        return ProductFilter._with_effective_price(queryset)
