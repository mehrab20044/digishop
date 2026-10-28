from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.exceptions import APIException, NotFound
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from payments.api.v1.serializers import (
    FakePaymentDecisionSerializer,
    FakePaymentPageSerializer,
    PaymentSerializer,
    PaymentStartResponseSerializer,
    PaymentStartSerializer,
)
from payments.gateways.base import (
    GatewayConfigurationError,
    GatewayUnavailableError,
)
from payments.gateways.fake import require_fake_gateway
from payments.models import FakeGatewaySession, Payment
from payments.services.fake_payment_service import (
    decide_fake_payment,
    verify_fake_payment,
)
from payments.services.payment_service import start_payment


class PaymentServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = (
        "سرویس پرداخت موقتاً در دسترس نیست. "
        "وضعیت پرداخت قبلی را بررسی کنید."
    )
    default_code = "payment_unavailable"


def call_payment_service(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except (GatewayConfigurationError, GatewayUnavailableError) as exc:
        raise PaymentServiceUnavailable() from exc


class FakePaymentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)

        try:
            require_fake_gateway()
        except GatewayConfigurationError as exc:
            raise NotFound(
                "پرداخت آزمایشی در دسترس نیست."
            ) from exc


class PaymentStartView(FakePaymentAPIView):
    @extend_schema(
        request=PaymentStartSerializer,
        responses={
            200: PaymentStartResponseSerializer,
            201: PaymentStartResponseSerializer,
        },
    )
    def post(self, request):
        serializer = PaymentStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = call_payment_service(
            start_payment,
            request.user,
            **serializer.validated_data,
        )

        response = PaymentStartResponseSerializer(
            {
                "payment": result.payment,
                "redirect_url": result.redirect_url,
            },
            context={"request": request},
        )

        return Response(
            response.data,
            status=(
                status.HTTP_201_CREATED
                if result.created
                else status.HTTP_200_OK
            ),
        )


class PaymentDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return Payment.objects.filter(
            order__user=self.request.user,
        )


class FakePaymentPageView(FakePaymentAPIView):
    @extend_schema(
        responses={200: FakePaymentPageSerializer},
    )
    def get(self, request, pk):
        payment = get_object_or_404(
            Payment.objects.select_related("order").filter(
                order__user=request.user,
                gateway="fake",
            ),
            pk=pk,
        )
        session = (
            FakeGatewaySession.objects.filter(payment=payment)
            .first()
        )

        if session is None:
            raise PaymentServiceUnavailable()

        now = timezone.now()
        can_decide = (
            payment.status == Payment.Status.PENDING
            and payment.order.status == Order.Status.PENDING_PAYMENT
            and session.status == FakeGatewaySession.Status.PENDING
            and payment.expires_at > now
            and payment.order.expires_at > now
            and session.expires_at > now
        )

        serializer = FakePaymentPageSerializer(
            {
                "payment": payment,
                "can_decide": can_decide,
                "is_test": True,
            },
            context={"request": request},
        )

        return Response(serializer.data)


class FakePaymentDecisionView(FakePaymentAPIView):
    @extend_schema(
        request=FakePaymentDecisionSerializer,
        responses={200: PaymentSerializer},
    )
    def post(self, request, pk):
        serializer = FakePaymentDecisionSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        payment = call_payment_service(
            decide_fake_payment,
            request.user,
            payment_id=pk,
            **serializer.validated_data,
        )

        return Response(
            PaymentSerializer(
                payment,
                context={"request": request},
            ).data,
        )


class FakePaymentVerifyView(FakePaymentAPIView):
    @extend_schema(
        request=None,
        responses={200: PaymentSerializer},
    )
    def post(self, request, pk):
        payment = call_payment_service(
            verify_fake_payment,
            request.user,
            payment_id=pk,
        )

        return Response(
            PaymentSerializer(
                payment,
                context={"request": request},
            ).data,
        )