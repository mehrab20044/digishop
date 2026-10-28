from rest_framework import serializers

from payments.models import Payment


class PaymentStartSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    request_id = serializers.UUIDField()


class FakePaymentDecisionSerializer(serializers.Serializer):
    outcome = serializers.ChoiceField(
        choices=["success", "cancel"],
    )


class PaymentSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "order_id",
            "gateway",
            "amount",
            "currency",
            "status",
            "status_label",
            "reference_id",
            "expires_at",
            "verified_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PaymentStartResponseSerializer(serializers.Serializer):
    payment = PaymentSerializer(read_only=True)
    redirect_url = serializers.CharField(
        read_only=True,
        allow_null=True,
    )


class FakePaymentPageSerializer(serializers.Serializer):
    payment = PaymentSerializer(read_only=True)
    can_decide = serializers.BooleanField(read_only=True)
    is_test = serializers.BooleanField(read_only=True)