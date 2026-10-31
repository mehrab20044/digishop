from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.api.v1.customer_hub import order_data, paginated, return_data
from dashboard.api.v1.views import OwnerAPIView
from orders.models import Order, ReturnRequest, StoreSettings
from orders.services.customer_hub_service import (
    advance_order,
    return_policy,
    review_return,
)


class ShipmentInput(serializers.Serializer):
    order_id = serializers.UUIDField()
    expected_status = serializers.ChoiceField(choices=Order.Status.choices)
    status = serializers.ChoiceField(choices=["shipped", "delivered"])
    carrier = serializers.CharField(max_length=100, required=False, allow_blank=True)
    tracking_code = serializers.CharField(
        max_length=120, required=False, allow_blank=True
    )
    tracking_url = serializers.URLField(
        max_length=1000, required=False, allow_blank=True
    )
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)


class ReviewInput(serializers.Serializer):
    request_id = serializers.IntegerField(min_value=1)
    expected_status = serializers.ChoiceField(choices=ReturnRequest.Status.choices)
    status = serializers.ChoiceField(choices=ReturnRequest.Status.choices)
    note = serializers.CharField(max_length=1000)


class PolicyInput(serializers.Serializer):
    enabled = serializers.BooleanField()
    days = serializers.IntegerField(min_value=1, max_value=365)


class CustomerOperationsView(OwnerAPIView):
    http_method_names = ["get", "post", "patch", "head", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.has_perm("orders.view_order"):
            raise PermissionDenied("مجوز مشاهده سفارش‌ها ندارید.")

    def get(self, request):
        kind = request.query_params.get("kind", "orders")
        if kind == "policy":
            return Response(
                {
                    **return_policy(),
                    "editable": request.user.has_perm("orders.change_storesettings"),
                }
            )
        if kind == "returns":
            if not request.user.has_perm("orders.view_returnrequest"):
                raise PermissionDenied("مجوز مشاهده مرجوعی‌ها ندارید.")
            return paginated(
                request,
                ReturnRequest.objects.select_related("order").prefetch_related(
                    "order__items"
                ),
                lambda row: {
                    **return_data(row),
                    "can_review": request.user.has_perm("orders.change_returnrequest"),
                },
                self,
            )
        rows = (
            Order.objects.select_related("shipment", "return_request")
            .prefetch_related("items", "events")
            .order_by("-created_at", "-pk")
        )
        status = request.query_params.get("status", "")
        if status:
            if status not in Order.Status.values:
                raise serializers.ValidationError("وضعیت معتبر نیست.")
            rows = rows.filter(status=status)
        policy = return_policy()

        def document(row):
            result = order_data(row, request, policy)
            result["can_change"] = request.user.has_perm("orders.change_order")
            return result

        return paginated(request, rows, document, self)

    def post(self, request):
        serializer = ShipmentInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = advance_order(request.user, **serializer.validated_data)
        return Response(order_data(row, request))

    def patch(self, request):
        if "request_id" in request.data:
            serializer = ReviewInput(data=request.data)
            serializer.is_valid(raise_exception=True)
            return Response(
                return_data(review_return(request.user, **serializer.validated_data))
            )
        if not request.user.has_perm("orders.change_storesettings"):
            raise PermissionDenied("مجوز تنظیم سیاست مرجوعی ندارید.")
        serializer = PolicyInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            row = StoreSettings.objects.select_for_update().first()
            if not row:
                raise serializers.ValidationError(
                    "ابتدا هزینه ارسال را در تنظیمات فروشگاه ثبت کنید."
                )
            row.returns_enabled = serializer.validated_data["enabled"]
            row.return_days = serializer.validated_data["days"]
            row.save(update_fields=["returns_enabled", "return_days", "updated_at"])
        return Response(return_policy())
