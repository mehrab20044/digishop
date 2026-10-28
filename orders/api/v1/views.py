from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.v1.serializers import (
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderPreviewRequestSerializer,
    OrderPreviewSerializer,
)
from orders.models import Order
from orders.services.order_service import (
    cancel_order,
    create_order,
    preview_order,
)


class OrderPagination(PageNumberPagination):
    page_size = 12
    max_page_size = 50
    page_size_query_param = "page_size"


class OrderListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]
    pagination_class = OrderPagination

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user,
        ).order_by("-created_at", "-id")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return OrderCreateSerializer

        return OrderListSerializer

    @extend_schema(
        request=OrderCreateSerializer,
        responses={
            200: OrderDetailSerializer,
            201: OrderDetailSerializer,
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order, created = create_order(
            request.user,
            **serializer.validated_data,
        )

        result = OrderDetailSerializer(
            order,
            context=self.get_serializer_context(),
        )

        return Response(
            result.data,
            status=(
                status.HTTP_201_CREATED
                if created
                else status.HTTP_200_OK
            ),
        )


class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderDetailSerializer

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user,
        ).prefetch_related("items")


class OrderCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(
        request=None,
        responses={200: OrderDetailSerializer},
    )
    def post(self, request, pk):
        order = cancel_order(
            request.user,
            order_id=pk,
        )

        serializer = OrderDetailSerializer(
            order,
            context={"request": request},
        )

        return Response(serializer.data)

class OrderPreviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(
        request=OrderPreviewRequestSerializer,
        responses={200: OrderPreviewSerializer},
    )
    def post(self, request):
        serializer = OrderPreviewRequestSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        preview = preview_order(
            request.user,
            **serializer.validated_data,
        )

        result = OrderPreviewSerializer(
            preview,
            context={"request": request},
        )

        return Response(result.data)