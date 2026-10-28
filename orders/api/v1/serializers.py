from rest_framework import serializers

from orders.models import Order, OrderItem


class OrderCreateSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(min_value=1)
    request_id = serializers.UUIDField()
    expected_total = serializers.IntegerField(min_value=1)
    customer_note = serializers.CharField(
        max_length=1000,
        required=False,
        default="",
        allow_blank=True,
        trim_whitespace=True,
    )


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product_id",
            "variant_id",
            "product_name",
            "product_slug",
            "variant_name",
            "sku",
            "had_variant",
            "quantity",
            "unit_price",
            "line_total",
        )
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Order
        fields = (
            "id",
            "status",
            "status_label",
            "currency",
            "subtotal",
            "shipping_cost",
            "total",
            "expires_at",
            "paid_at",
            "cancelled_at",
            "expired_at",
            "shipped_at",
            "delivered_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrderDetailSerializer(OrderListSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + (
            "recipient_name",
            "recipient_phone",
            "province",
            "city",
            "street_address",
            "building_number",
            "unit",
            "postal_code",
            "customer_note",
            "items",
        )
        read_only_fields = fields


class OrderPreviewRequestSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(min_value=1)


class OrderAddressSnapshotSerializer(serializers.Serializer):
    recipient_name = serializers.CharField(read_only=True)
    recipient_phone = serializers.CharField(read_only=True)
    province = serializers.CharField(read_only=True)
    city = serializers.CharField(read_only=True)
    street_address = serializers.CharField(read_only=True)
    building_number = serializers.CharField(read_only=True)
    unit = serializers.CharField(read_only=True, allow_blank=True)
    postal_code = serializers.CharField(read_only=True)


class OrderPreviewItemSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(read_only=True)
    variant_id = serializers.IntegerField(
        read_only=True,
        allow_null=True,
    )
    product_name = serializers.CharField(read_only=True)
    variant_name = serializers.CharField(
        read_only=True,
        allow_blank=True,
    )
    quantity = serializers.IntegerField(read_only=True)
    unit_price = serializers.IntegerField(read_only=True)
    line_total = serializers.IntegerField(read_only=True)


class OrderPreviewSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(read_only=True)
    address = OrderAddressSnapshotSerializer(read_only=True)
    currency = serializers.CharField(read_only=True)
    items = OrderPreviewItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    subtotal = serializers.IntegerField(read_only=True)
    shipping_cost = serializers.IntegerField(read_only=True)
    total = serializers.IntegerField(read_only=True)
    reservation_minutes = serializers.IntegerField(read_only=True)