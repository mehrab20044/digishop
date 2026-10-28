from uuid import uuid4

from django.conf import settings
from django.db import models


class StoreSettings(models.Model):
    id = models.PositiveSmallIntegerField(
        primary_key=True,
        default=1,
        editable=False,
    )
    shipping_cost = models.PositiveBigIntegerField(
        "هزینه ارسال (تومان)",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تنظیمات فروشگاه"
        verbose_name_plural = "تنظیمات فروشگاه"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1),
                name="orders_store_settings_singleton",
            ),
        ]

    def __str__(self):
        return "تنظیمات فروشگاه"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "در انتظار پرداخت"
        PAID = "paid", "پرداخت‌شده"
        SHIPPED = "shipped", "ارسال‌شده"
        DELIVERED = "delivered", "تحویل‌شده"
        CANCELLED = "cancelled", "لغوشده"
        EXPIRED = "expired", "منقضی‌شده"

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )

    request_id = models.UUIDField()
    request_fingerprint = models.CharField(
        max_length=64,
        editable=False,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )

    recipient_name = models.CharField(max_length=150)
    recipient_phone = models.CharField(max_length=11)
    province = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    street_address = models.CharField(max_length=500)
    building_number = models.CharField(max_length=20)
    unit = models.CharField(max_length=20, blank=True)
    postal_code = models.CharField(max_length=10)

    currency = models.CharField(
        max_length=3,
        default="IRT",
        editable=False,
    )
    subtotal = models.PositiveBigIntegerField()
    shipping_cost = models.PositiveBigIntegerField()
    total = models.PositiveBigIntegerField()

    customer_note = models.CharField(
        max_length=1000,
        blank=True,
    )

    expires_at = models.DateTimeField()
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["status", "expires_at"],
                name="orders_pending_expiry_idx",
            ),
            models.Index(
                fields=["user", "-created_at"],
                name="orders_user_created_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "request_id"],
                name="orders_unique_user_request",
            ),
            models.CheckConstraint(
                condition=models.Q(subtotal__gt=0),
                name="orders_subtotal_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    total=models.F("subtotal")
                    + models.F("shipping_cost"),
                ),
                name="orders_total_matches_amounts",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IRT"),
                name="orders_currency_toman",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending_payment",
                        "paid",
                        "shipped",
                        "delivered",
                        "cancelled",
                        "expired",
                    ],
                ),
                name="orders_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    expires_at__gt=models.F("created_at"),
                ),
                name="orders_expiry_after_creation",
            ),
        ]

    def __str__(self):
        return str(self.pk)


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )

    selection_key = models.CharField(max_length=100)
    product_name = models.CharField(max_length=200)
    product_slug = models.CharField(max_length=220)
    variant_name = models.CharField(max_length=210, blank=True)
    sku = models.CharField(max_length=100, blank=True)
    had_variant = models.BooleanField(default=False)

    quantity = models.PositiveIntegerField()
    unit_price = models.PositiveBigIntegerField()
    line_total = models.PositiveBigIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "selection_key"],
                name="orders_unique_item_selection",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    quantity__gte=1,
                    quantity__lte=99,
                ),
                name="orders_item_quantity_range",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gt=0),
                name="orders_item_price_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    line_total=models.F("unit_price")
                    * models.F("quantity"),
                ),
                name="orders_item_total_matches",
            ),
        ]

    def __str__(self):
        return f"{self.product_name} × {self.quantity}"