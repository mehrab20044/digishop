from datetime import timedelta
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from orders.models import Order, OrderEvent, ReturnRequest, Shipment, StoreSettings


def return_policy():
    row = StoreSettings.objects.first()
    return {
        "enabled": bool(row and row.returns_enabled),
        "days": row.return_days if row else 7,
    }


def can_request_return(order, policy=None):
    policy = policy or return_policy()
    return bool(
        policy["enabled"]
        and order.status == Order.Status.DELIVERED
        and order.delivered_at
        and order.delivered_at
        <= timezone.now()
        <= order.delivered_at + timedelta(days=policy["days"])
    )


@transaction.atomic
def request_return(user, order_id, reason, items):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    order = get_object_or_404(
        Order.objects.select_for_update().filter(user=user), pk=order_id
    )
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError("دلیل درخواست معتبر را وارد کنید.")
    if not isinstance(items, list) or any(
        not isinstance(item, dict)
        or set(item) != {"item_id", "quantity"}
        or type(item["item_id"]) is not int
        or type(item["quantity"]) is not int
        for item in items
    ):
        raise ValidationError("ساختار کالاهای مرجوعی معتبر نیست.")
    existing = ReturnRequest.objects.filter(order=order).first()
    normalized = sorted(items, key=lambda row: row["item_id"])
    if existing:
        if existing.reason == reason and existing.items == normalized:
            return existing, False
        raise ValidationError("برای این سفارش قبلاً درخواست ثبت شده است.")
    if not can_request_return(order):
        raise ValidationError(
            "این سفارش در مهلت یا شرایط مجاز ثبت درخواست مرجوعی نیست."
        )
    order_items = {item.pk: item for item in order.items.all()}
    if (
        not normalized
        or len(normalized) > len(order_items)
        or len({row["item_id"] for row in normalized}) != len(normalized)
    ):
        raise ValidationError("کالاهای مرجوعی را درست انتخاب کنید.")
    for row in normalized:
        item = order_items.get(row["item_id"])
        if item is None or not 1 <= row["quantity"] <= item.quantity:
            raise ValidationError("کالا یا تعداد مرجوعی معتبر نیست.")
    return ReturnRequest.objects.create(
        order=order, reason=reason, items=normalized
    ), True


@transaction.atomic
def advance_order(
    actor,
    order_id,
    expected_status,
    status,
    carrier="",
    tracking_code="",
    tracking_url="",
    note="",
):
    if not actor.is_staff or not actor.has_perm("orders.change_order"):
        raise PermissionDenied("مجوز تغییر سفارش ندارید.")
    order = get_object_or_404(Order.objects.select_for_update(), pk=order_id)
    if order.status != expected_status:
        raise ValidationError("وضعیت سفارش تغییر کرده؛ اطلاعات را تازه کنید.")
    allowed = {
        Order.Status.PAID: Order.Status.SHIPPED,
        Order.Status.SHIPPED: Order.Status.DELIVERED,
    }
    if allowed.get(order.status) != status:
        raise ValidationError("این تغییر وضعیت مجاز نیست.")
    if status == Order.Status.SHIPPED:
        if not carrier.strip() or not tracking_code.strip():
            raise ValidationError("روش ارسال و کد رهگیری الزامی‌اند.")
        if tracking_url:
            url = urlsplit(tracking_url)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or "\\" in tracking_url
            ):
                raise ValidationError("لینک رهگیری باید آدرس معتبر https باشد.")
        Shipment.objects.update_or_create(
            order=order,
            defaults={
                "carrier": carrier,
                "tracking_code": tracking_code,
                "tracking_url": tracking_url,
            },
        )
        order.shipped_at = timezone.now()
    else:
        order.delivered_at = timezone.now()
    order.status = status
    order.save(update_fields=["status", "shipped_at", "delivered_at", "updated_at"])
    OrderEvent.objects.create(order=order, status=status, note=note, actor=actor)
    return order


@transaction.atomic
def review_return(actor, request_id, expected_status, status, note):
    if not actor.is_staff or not actor.has_perm("orders.change_returnrequest"):
        raise PermissionDenied("مجوز بررسی مرجوعی ندارید.")
    row = get_object_or_404(ReturnRequest.objects.select_for_update(), pk=request_id)
    if row.status != expected_status:
        raise ValidationError("درخواست تغییر کرده؛ نسخه جدید را دریافت کنید.")
    allowed = {"requested": {"approved", "rejected"}, "approved": {"received"}}
    if status not in allowed.get(row.status, set()) or not note.strip():
        raise ValidationError(
            "تغییر وضعیت معتبر و توضیح قابل نمایش به مشتری الزامی است."
        )
    row.status, row.manager_note, row.reviewed_by = status, note, actor
    row.save(update_fields=["status", "manager_note", "reviewed_by", "updated_at"])
    # Receipt is not a refund or a stock movement. Those require their own flow.
    return row
