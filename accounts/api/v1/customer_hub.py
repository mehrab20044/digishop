from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework import permissions, serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import SavedProduct
from accounts.services.customer_hub_service import save_product
from orders.api.v1.serializers import OrderDetailSerializer
from orders.models import Order, ReturnRequest
from orders.services.customer_hub_service import (
    can_request_return,
    request_return,
    return_policy,
)


class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_active
            and request.auth
            and request.auth.get("purpose") == "customer"
        )


@method_decorator(never_cache, name="dispatch")
class CustomerAPIView(APIView):
    permission_classes = [IsCustomer]
    parser_classes = [JSONParser]


class HubPagination(PageNumberPagination):
    page_size = 12


def paginated(request, queryset, convert, view):
    paginator = HubPagination()
    rows = paginator.paginate_queryset(queryset, request, view=view)
    return paginator.get_paginated_response([convert(row) for row in rows])


def return_data(row):
    order_items = {item.pk: item for item in row.order.items.all()}
    details = []
    for selected in row.items:
        item = order_items.get(selected["item_id"])
        details.append(
            {
                "item_id": selected["item_id"],
                "quantity": selected["quantity"],
                "name": item.product_name if item else "کالا",
                "variant": item.variant_name if item else "",
            }
        )
    return {
        "id": row.pk,
        "order_id": str(row.order_id),
        "status": row.status,
        "status_label": row.get_status_display(),
        "reason": row.reason,
        "items": row.items,
        "item_details": details,
        "manager_note": row.manager_note,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def order_data(order, request, policy=None):
    policy = policy if policy is not None else return_policy()
    data = dict(OrderDetailSerializer(order, context={"request": request}).data)
    data["return_policy"] = policy
    shipment = getattr(order, "shipment", None)
    data["shipment"] = (
        {
            "carrier": shipment.carrier,
            "tracking_code": shipment.tracking_code,
            "tracking_url": shipment.tracking_url,
        }
        if shipment
        else None
    )
    events = [
        {"status": row.status, "note": row.note, "created_at": row.created_at}
        for row in order.events.all()
    ]
    recorded = {event["status"] for event in events}
    for status, timestamp in [
        ("pending_payment", order.created_at),
        ("paid", order.paid_at),
        ("shipped", order.shipped_at),
        ("delivered", order.delivered_at),
        ("cancelled", order.cancelled_at),
        ("expired", order.expired_at),
    ]:
        if timestamp and status not in recorded:
            events.append({"status": status, "note": "", "created_at": timestamp})
    data["events"] = sorted(events, key=lambda event: event["created_at"])
    returned = getattr(order, "return_request", None)
    data["return_request"] = return_data(returned) if returned else None
    data["can_request_return"] = not returned and can_request_return(order, policy)
    return data


def orders_for(user):
    return (
        Order.objects.filter(user=user)
        .select_related("shipment", "return_request")
        .prefetch_related("items", "events")
        .order_by("-created_at", "-pk")
    )


class HubSummaryView(CustomerAPIView):
    def get(self, request):
        counts = {
            row["status"]: row["count"]
            for row in Order.objects.filter(user=request.user)
            .values("status")
            .annotate(count=Count("id"))
        }
        policy = return_policy()
        return Response(
            {
                "counts": {key: counts.get(key, 0) for key in Order.Status.values},
                "returns_count": ReturnRequest.objects.filter(
                    order__user=request.user
                ).count(),
                "recent_orders": [
                    order_data(row, request, policy)
                    for row in orders_for(request.user)[:3]
                ],
                "return_policy": policy,
            }
        )


class HubOrdersView(CustomerAPIView):
    def get(self, request, pk=None):
        rows = orders_for(request.user)
        policy = return_policy()
        if pk is not None:
            return Response(order_data(get_object_or_404(rows, pk=pk), request, policy))
        status = request.query_params.get("status", "")
        if status:
            if status not in Order.Status.values:
                raise serializers.ValidationError("وضعیت سفارش معتبر نیست.")
            rows = rows.filter(status=status)
        return paginated(
            request, rows, lambda row: order_data(row, request, policy), self
        )


class SavedInput(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=SavedProduct.Kind.choices)
    enabled = serializers.BooleanField()


def saved_data(row):
    product = row.product
    public = product.is_active and product.status == "published"
    variants = list(product.variants.all())
    active = [v for v in variants if v.is_active and v.stock > 0 and v.price > 0]
    available = public and (
        bool(active) if variants else product.stock > 0 and product.price > 0
    )
    price = (
        min(v.price for v in active)
        if active
        else product.price
        if not variants and available
        else None
    )
    image = next((i for i in product.images.all() if i.is_primary), None)
    return {
        "id": row.pk,
        "kind": row.kind,
        "product_id": product.pk,
        "name": product.name if public else "کالای خارج از دسترس",
        "public": public,
        "available": bool(available),
        "price": price if available else None,
        "image": image.image.url if public and image and image.image else None,
    }


class SavedProductsView(CustomerAPIView):
    def get(self, request):
        kind = request.query_params.get("kind", "favorite")
        if kind not in SavedProduct.Kind.values:
            raise serializers.ValidationError("فهرست معتبر نیست.")
        rows = (
            SavedProduct.objects.filter(user=request.user, kind=kind)
            .select_related("product")
            .prefetch_related("product__images", "product__variants")
        )
        return paginated(request, rows, saved_data, self)

    def post(self, request):
        serializer = SavedInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        save_product(request.user, **serializer.validated_data)
        return Response({"saved": serializer.validated_data["enabled"]})


class ReturnItemInput(serializers.Serializer):
    item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class ReturnInput(serializers.Serializer):
    order_id = serializers.UUIDField()
    reason = serializers.CharField(max_length=1000, allow_blank=False)
    items = ReturnItemInput(many=True, allow_empty=False, max_length=100)


class ReturnsView(CustomerAPIView):
    def get(self, request):
        rows = (
            ReturnRequest.objects.filter(order__user=request.user)
            .select_related("order")
            .prefetch_related("order__items")
        )
        return paginated(request, rows, return_data, self)

    def post(self, request):
        serializer = ReturnInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        row, created = request_return(request.user, **serializer.validated_data)
        return Response(return_data(row), status=201 if created else 200)


class SavedStateView(CustomerAPIView):
    def get(self, request, pk):
        kinds = list(
            SavedProduct.objects.filter(user=request.user, product_id=pk).values_list(
                "kind", flat=True
            )
        )
        return Response({"favorite": "favorite" in kinds, "later": "later" in kinds})
