from uuid import uuid4

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from orders.models import Order
from orders.services.order_service import expire_order
from payments.gateways.base import (
    GatewayConfigurationError,
    VerificationRequest,
    VerificationStatus,
)
from payments.gateways.fake import FakeGateway, require_fake_gateway
from payments.models import FakeGatewaySession, Payment
from payments.services.payment_service import _lock_user, _uuid


def _lock_context(user, payment_id):
    payment_id = _uuid(payment_id, "payment_id")
    user = _lock_user(user)

    # Ownership is checked before returning any payment information.
    order_id = get_object_or_404(
        Payment.objects.filter(order__user=user),
        pk=payment_id,
    ).order_id

    order = Order.objects.select_for_update().get(
        pk=order_id,
        user=user,
    )
    payment = Payment.objects.select_for_update().get(
        pk=payment_id,
        order=order,
    )

    if payment.gateway != "fake":
        raise ValidationError({
            "payment_id": "این پرداخت متعلق به درگاه آزمایشی نیست.",
        })

    session = (
        FakeGatewaySession.objects.select_for_update()
        .filter(payment=payment)
        .first()
    )

    if session is None:
        raise GatewayConfigurationError(
            "The fake payment session is missing."
        )

    return order, payment, session


def _save_status(payment, status, failure_code=""):
    payment.status = status
    payment.failure_code = failure_code
    payment.save(update_fields=[
        "status",
        "failure_code",
        "updated_at",
    ])
    return payment


def _expire_pending_payment(order, payment):
    if (
        order.status == Order.Status.PENDING_PAYMENT
        and order.expires_at <= timezone.now()
    ):
        expire_order(order_id=order.pk)

    return _save_status(
        payment,
        Payment.Status.EXPIRED,
        "payment_expired",
    )


def _verify_locked(order, payment):
    if payment.status in {
        Payment.Status.SUCCEEDED,
        Payment.Status.FAILED,
        Payment.Status.CANCELLED,
        Payment.Status.EXPIRED,
        Payment.Status.REVIEW_REQUIRED,
    }:
        return payment

    if not payment.authority:
        return _save_status(
            payment,
            Payment.Status.REVIEW_REQUIRED,
            "missing_authority",
        )

    result = FakeGateway().verify(
        VerificationRequest(
            payment_id=payment.pk,
            authority=payment.authority,
            expected_amount=payment.amount,
            currency=payment.currency,
        ),
    )

    if result.status == VerificationStatus.SUCCEEDED:
        receipt_valid = (
            result.authority == payment.authority
            and bool(result.reference_id)
            and len(result.reference_id) <= 255
            and result.amount == payment.amount
            and result.currency == payment.currency
            and payment.amount == order.total
            and payment.currency == order.currency
        )

        if not receipt_valid:
            return _save_status(
                payment,
                Payment.Status.REVIEW_REQUIRED,
                "verification_mismatch",
            )

        # Preserve the verified receipt even if the order can no longer
        # be fulfilled. Never silently discard a successful transaction.
        payment.reference_id = result.reference_id
        payment.verified_at = timezone.now()
        payment.save(update_fields=[
            "reference_id",
            "verified_at",
            "updated_at",
        ])

        now = timezone.now()

        if order.status != Order.Status.PENDING_PAYMENT:
            return _save_status(
                payment,
                Payment.Status.REVIEW_REQUIRED,
                "order_not_payable",
            )

        if (
            order.expires_at <= now
            or payment.expires_at <= now
        ):
            if order.expires_at <= now:
                expire_order(order_id=order.pk)

            return _save_status(
                payment,
                Payment.Status.REVIEW_REQUIRED,
                "verified_after_deadline",
            )

        payment.status = Payment.Status.SUCCEEDED
        payment.failure_code = ""
        payment.save(update_fields=[
            "status",
            "failure_code",
            "updated_at",
        ])

        order.status = Order.Status.PAID
        order.paid_at = payment.verified_at
        order.save(update_fields=[
            "status",
            "paid_at",
            "updated_at",
        ])

        # Stock was already reserved during checkout.
        # Successful payment must not deduct it again.
        return payment

    if result.status == VerificationStatus.FAILED:
        if result.error_code == "payment_expired":
            return _expire_pending_payment(order, payment)

        status = (
            Payment.Status.CANCELLED
            if result.error_code == "customer_cancelled"
            else Payment.Status.FAILED
        )

        # A failed attempt does not cancel the order.
        return _save_status(
            payment,
            status,
            result.error_code or "gateway_rejected",
        )

    if result.status == VerificationStatus.PENDING:
        if (
            order.expires_at <= timezone.now()
            or payment.expires_at <= timezone.now()
        ):
            return _expire_pending_payment(order, payment)

        if order.status != Order.Status.PENDING_PAYMENT:
            return _save_status(
                payment,
                Payment.Status.CANCELLED,
                "order_not_payable",
            )

        return payment

    return _save_status(
        payment,
        Payment.Status.REVIEW_REQUIRED,
        result.error_code or "verification_unknown",
    )


@transaction.atomic
def verify_fake_payment(user, *, payment_id):
    require_fake_gateway()
    order, payment, _ = _lock_context(user, payment_id)
    return _verify_locked(order, payment)


@transaction.atomic
def decide_fake_payment(user, *, payment_id, outcome):
    require_fake_gateway()

    if outcome not in {"success", "cancel"}:
        raise ValidationError({
            "outcome": "نتیجه باید success یا cancel باشد.",
        })

    order, payment, session = _lock_context(user, payment_id)

    target_status = (
        FakeGatewaySession.Status.SUCCEEDED
        if outcome == "success"
        else FakeGatewaySession.Status.CANCELLED
    )

    # The first accepted decision is immutable.
    if session.status != FakeGatewaySession.Status.PENDING:
        if session.status != target_status:
            raise ValidationError({
                "outcome": "نتیجهٔ این پرداخت قبلاً ثبت شده است.",
            })

        return _verify_locked(order, payment)

    if payment.status != Payment.Status.PENDING:
        raise ValidationError({
            "payment_id": "این تلاش پرداخت دیگر قابل انجام نیست.",
        })

    now = timezone.now()

    if (
        order.expires_at <= now
        or payment.expires_at <= now
        or session.expires_at <= now
    ):
        return _expire_pending_payment(order, payment)

    if order.status != Order.Status.PENDING_PAYMENT:
        return _save_status(
            payment,
            Payment.Status.CANCELLED,
            "order_not_payable",
        )

    session.status = target_status
    session.decided_at = now
    session.reference_id = (
        uuid4()
        if outcome == "success"
        else None
    )
    session.save(update_fields=[
        "status",
        "decided_at",
        "reference_id",
    ])

    return _verify_locked(order, payment)