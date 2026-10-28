from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from orders.models import Order
from payments.gateways.base import (
    GatewayConfigurationError,
    InitiationStatus,
    PaymentRequest,
)
from payments.gateways.fake import FakeGateway, require_fake_gateway
from payments.models import Payment

User = get_user_model()

ACTIVE_STATUSES = (
    Payment.Status.CREATED,
    Payment.Status.PENDING,
    Payment.Status.VERIFYING,
    Payment.Status.REVIEW_REQUIRED,
)


@dataclass(frozen=True, slots=True)
class PaymentStartResult:
    payment: Payment
    redirect_url: str | None
    created: bool


def _uuid(value, field):
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError({
            field: "شناسه معتبر نیست.",
        }) from exc


def _lock_user(user):
    if not user or not user.is_authenticated:
        raise PermissionDenied("ابتدا وارد حساب شوید.")

    current = User.objects.select_for_update().get(pk=user.pk)

    if not current.is_active:
        raise PermissionDenied("حساب کاربری فعال نیست.")

    return current


def _existing_result(payment):
    redirect_url = None

    if payment.status == Payment.Status.PENDING:
        if payment.gateway != "fake" or not payment.authority:
            raise GatewayConfigurationError(
                "Pending payment has invalid gateway information."
            )

        redirect_url = f"/payments/fake/{payment.pk}"

    return PaymentStartResult(
        payment=payment,
        redirect_url=redirect_url,
        created=False,
    )


@transaction.atomic
def start_payment(user, *, order_id, request_id):
    """
    Start a payment using the local fake gateway.

    This transaction contains only database operations.
    A real gateway's network calls must not be added inside it.
    """
    order_id = _uuid(order_id, "order_id")
    request_id = _uuid(request_id, "request_id")

    require_fake_gateway()

    # Match the lock order used by order cancellation and expiration:
    # user -> order -> payment.
    user = _lock_user(user)

    order = get_object_or_404(
        Order.objects.select_for_update().filter(user=user),
        pk=order_id,
    )

    previous = (
        Payment.objects.select_for_update()
        .filter(
            order=order,
            request_id=request_id,
        )
        .first()
    )

    if previous is not None:
        return _existing_result(previous)

    if order.status != Order.Status.PENDING_PAYMENT:
        raise ValidationError({
            "order_id": "این سفارش در وضعیت قابل پرداخت نیست.",
        })

    now = timezone.now()

    if order.expires_at <= now + timedelta(seconds=1):
        raise ValidationError({
            "order_id": "مهلت پرداخت سفارش پایان یافته است.",
        })

    if order.currency != "IRT" or order.total <= 0:
        raise ValidationError({
            "order_id": "مبلغ یا واحد پول سفارش معتبر نیست.",
        })

    if Payment.objects.filter(
        order=order,
        status=Payment.Status.SUCCEEDED,
    ).exists():
        raise ValidationError({
            "order_id": "برای این سفارش پرداخت موفق ثبت شده است.",
        })

    active = (
        Payment.objects.select_for_update()
        .filter(
            order=order,
            status__in=ACTIVE_STATUSES,
        )
        .first()
    )

    if active is not None:
        if active.status == Payment.Status.PENDING:
            return _existing_result(active)

        raise ValidationError({
            "payment": (
                "یک تلاش پرداخت در حال بررسی است؛ "
                "ابتدا وضعیت همان پرداخت را بررسی کنید."
            ),
        })

    payment = Payment.objects.create(
        order=order,
        request_id=request_id,
        gateway="fake",
        amount=order.total,
        currency=order.currency,
        expires_at=order.expires_at,
    )

    gateway = FakeGateway()

    result = gateway.initiate(
        PaymentRequest(
            payment_id=payment.pk,
            order_id=order.pk,
            amount=payment.amount,
            currency=payment.currency,
            expires_at=payment.expires_at,
            # The fake gateway uses authenticated application endpoints;
            # it does not perform an external HTTP callback.
            callback_url="",
        ),
    )

    if result.status != InitiationStatus.ACCEPTED:
        # The fake adapter performs local database operations only,
        # so this exception safely rolls back the new attempt.
        raise GatewayConfigurationError(
            "The local fake gateway could not initiate the payment."
        )

    expected_redirect = f"/payments/fake/{payment.pk}"

    if (
        not result.authority
        or len(result.authority) > 255
        or result.redirect_url != expected_redirect
    ):
        raise GatewayConfigurationError(
            "The fake gateway returned invalid initiation information."
        )

    payment.authority = result.authority
    payment.status = Payment.Status.PENDING
    payment.save(update_fields=[
        "authority",
        "status",
        "updated_at",
    ])

    return PaymentStartResult(
        payment=payment,
        redirect_url=expected_redirect,
        created=True,
    )