from django.conf import settings
from django.db import models


class Shipment(models.Model):
    order = models.OneToOneField(
        "orders.Order", on_delete=models.CASCADE, related_name="shipment"
    )
    carrier = models.CharField(max_length=100)
    tracking_code = models.CharField(max_length=120)
    tracking_url = models.URLField(max_length=1000, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class OrderEvent(models.Model):
    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="events"
    )
    status = models.CharField(max_length=20)
    note = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]


class ReturnRequest(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "در انتظار بررسی"
        APPROVED = "approved", "تأیید ارسال مرجوعی"
        REJECTED = "rejected", "رد درخواست"
        RECEIVED = "received", "دریافت کالای مرجوعی"

    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="return_request"
    )
    reason = models.CharField(max_length=1000)
    items = models.JSONField(default=list)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.REQUESTED
    )
    manager_note = models.CharField(max_length=1000, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["requested", "approved", "rejected", "received"]
                ),
                name="orders_return_status_valid",
            )
        ]
