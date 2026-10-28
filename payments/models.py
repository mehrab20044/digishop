from uuid import uuid4

from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "ایجادشده"
        PENDING = "pending", "در انتظار پرداخت"
        VERIFYING = "verifying", "در حال بررسی پرداخت"
        SUCCEEDED = "succeeded", "پرداخت موفق"
        FAILED = "failed", "پرداخت ناموفق"
        CANCELLED = "cancelled", "انصراف از پرداخت"
        EXPIRED = "expired", "منقضی‌شده"
        REVIEW_REQUIRED = "review_required", "نیازمند بررسی"

    id = models.UUIDField(
        primary_key=True,
        default=uuid4,
        editable=False,
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payments",
    )

    # The client reuses this ID when retrying the same initiation request.
    request_id = models.UUIDField()

    # Gateway identifiers are selected and validated by the service.
    gateway = models.CharField(max_length=32)

    # A snapshot of the order amount; never accepted from the client.
    amount = models.PositiveBigIntegerField()
    currency = models.CharField(
        max_length=3,
        default="IRT",
        editable=False,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CREATED,
    )

    # Authority issued when the gateway accepts a payment request.
    authority = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        editable=False,
    )

    # Final transaction reference returned by server-side verification.
    reference_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        editable=False,
    )

    # Store normalized error codes, not secrets or raw gateway responses.
    failure_code = models.CharField(
        max_length=64,
        blank=True,
        editable=False,
    )

    expires_at = models.DateTimeField()
    verification_started_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["status", "expires_at"],
                name="payments_status_expiry_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["order", "request_id"],
                name="payments_unique_order_request",
            ),
            models.UniqueConstraint(
                fields=["gateway", "authority"],
                condition=models.Q(authority__isnull=False),
                name="payments_unique_gateway_auth",
            ),
            models.UniqueConstraint(
                fields=["gateway", "reference_id"],
                condition=models.Q(reference_id__isnull=False),
                name="payments_unique_gateway_ref",
            ),
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(
                    status__in=[
                        "created",
                        "pending",
                        "verifying",
                        "review_required",
                    ],
                ),
                name="payments_one_active_per_order",
            ),
            models.UniqueConstraint(
                fields=["order"],
                condition=models.Q(status="succeeded"),
                name="payments_one_success_per_order",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payments_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IRT"),
                name="payments_currency_toman",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "created",
                        "pending",
                        "verifying",
                        "succeeded",
                        "failed",
                        "cancelled",
                        "expired",
                        "review_required",
                    ],
                ),
                name="payments_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(status="succeeded")
                    | models.Q(
                        verified_at__isnull=False,
                        reference_id__isnull=False,
                    )
                ),
                name="payments_success_has_verification",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(authority__isnull=True)
                    | ~models.Q(authority="")
                ),
                name="payments_authority_not_empty",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(reference_id__isnull=True)
                    | ~models.Q(reference_id="")
                ),
                name="payments_reference_not_empty",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    expires_at__gt=models.F("created_at"),
                ),
                name="payments_expiry_after_creation",
            ),
        ]

    def __str__(self):
        return f"{self.pk} / {self.get_status_display()}"

class FakeGatewaySession(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار انتخاب"
        SUCCEEDED = "succeeded", "موفق آزمایشی"
        CANCELLED = "cancelled", "انصراف آزمایشی"

    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="fake_session",
    )

    authority = models.UUIDField(
        default=uuid4,
        unique=True,
        editable=False,
    )

    amount = models.PositiveBigIntegerField()
    currency = models.CharField(
        max_length=3,
        default="IRT",
        editable=False,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    reference_id = models.UUIDField(
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )

    expires_at = models.DateTimeField()
    decided_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payments_fake_amount_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(currency="IRT"),
                name="payments_fake_currency_toman",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pending",
                        "succeeded",
                        "cancelled",
                    ],
                ),
                name="payments_fake_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="pending",
                        decided_at__isnull=True,
                        reference_id__isnull=True,
                    )
                    | models.Q(
                        status="succeeded",
                        decided_at__isnull=False,
                        reference_id__isnull=False,
                    )
                    | models.Q(
                        status="cancelled",
                        decided_at__isnull=False,
                        reference_id__isnull=True,
                    )
                ),
                name="payments_fake_outcome_consistent",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    expires_at__gt=models.F("created_at"),
                ),
                name="payments_fake_expiry_valid",
            ),
        ]

    def __str__(self):
        return f"Fake / {self.authority}"