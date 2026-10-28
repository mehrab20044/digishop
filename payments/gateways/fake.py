from uuid import UUID

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from payments.gateways.base import (
    GatewayConfigurationError,
    InitiationResult,
    InitiationStatus,
    PaymentRequest,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
)
from payments.models import FakeGatewaySession, Payment


def require_fake_gateway():
    if (
        settings.DEBUG is not True
        or getattr(settings, "PAYMENTS_FAKE_ENABLED", False) is not True
    ):
        raise GatewayConfigurationError(
            "The fake payment gateway is disabled."
        )


class FakeGateway:
    code = "fake"

    @transaction.atomic
    def initiate(self, request: PaymentRequest) -> InitiationResult:
        require_fake_gateway()

        payment = (
            Payment.objects.select_for_update()
            .filter(pk=request.payment_id)
            .first()
        )

        if payment is None:
            raise GatewayConfigurationError(
                "Payment must exist before gateway initiation."
            )

        if (
            payment.gateway != self.code
            or payment.order_id != request.order_id
            or payment.amount != request.amount
            or payment.currency != request.currency
            or payment.expires_at != request.expires_at
        ):
            raise GatewayConfigurationError(
                "Gateway request does not match the payment."
            )

        if payment.status not in {
            Payment.Status.CREATED,
            Payment.Status.PENDING,
        }:
            return InitiationResult(
                status=InitiationStatus.REJECTED,
                error_code="payment_not_initiable",
            )

        if payment.expires_at <= timezone.now():
            return InitiationResult(
                status=InitiationStatus.REJECTED,
                error_code="payment_expired",
            )

        session, _ = FakeGatewaySession.objects.get_or_create(
            payment=payment,
            defaults={
                "amount": payment.amount,
                "currency": payment.currency,
                "expires_at": payment.expires_at,
            },
        )

        if (
            session.amount != payment.amount
            or session.currency != payment.currency
            or session.expires_at != payment.expires_at
        ):
            raise GatewayConfigurationError(
                "Fake session does not match the payment."
            )

        if session.status != FakeGatewaySession.Status.PENDING:
            return InitiationResult(
                status=InitiationStatus.REJECTED,
                error_code="fake_session_already_decided",
            )

        return InitiationResult(
            status=InitiationStatus.ACCEPTED,
            authority=str(session.authority),
            redirect_url=f"/payments/fake/{payment.pk}",
        )

    def verify(
        self,
        request: VerificationRequest,
    ) -> VerificationResult:
        require_fake_gateway()

        try:
            authority = UUID(str(request.authority))
        except (ValueError, TypeError, AttributeError):
            return VerificationResult(
                status=VerificationStatus.UNKNOWN,
                error_code="invalid_authority",
            )

        session = (
            FakeGatewaySession.objects.filter(
                payment_id=request.payment_id,
                payment__gateway=self.code,
                authority=authority,
            )
            .first()
        )

        if session is None:
            return VerificationResult(
                status=VerificationStatus.UNKNOWN,
                error_code="fake_session_not_found",
            )

        verified_authority = str(session.authority)

        if session.status == FakeGatewaySession.Status.SUCCEEDED:
            if session.reference_id is None:
                return VerificationResult(
                    status=VerificationStatus.UNKNOWN,
                    error_code="fake_reference_missing",
                )

            return VerificationResult(
                status=VerificationStatus.SUCCEEDED,
                authority=verified_authority,
                reference_id=str(session.reference_id),
                amount=session.amount,
                currency=session.currency,
            )

        if session.status == FakeGatewaySession.Status.CANCELLED:
            return VerificationResult(
                status=VerificationStatus.FAILED,
                authority=verified_authority,
                error_code="customer_cancelled",
            )

        if session.expires_at <= timezone.now():
            return VerificationResult(
                status=VerificationStatus.FAILED,
                authority=verified_authority,
                error_code="payment_expired",
            )

        return VerificationResult(
            status=VerificationStatus.PENDING,
            authority=verified_authority,
        )