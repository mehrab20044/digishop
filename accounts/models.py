from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .profile_validators import validate_avatar

phone_validator = RegexValidator(
    regex=r"\A09[0-9]{9}\Z",
    message="شماره موبایل معتبر نیست.",
)


class PhoneIdentity(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="phone_identity",
    )
    phone = models.CharField(
        max_length=11,
        unique=True,
        validators=[phone_validator],
    )
    verified_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.phone


class OTPChallenge(models.Model):
    phone = models.CharField(
        max_length=11,
        unique=True,
        validators=[phone_validator],
    )
    code_hash = models.CharField(max_length=128, blank=True)
    expires_at = models.DateTimeField()
    last_sent_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    send_window_started_at = models.DateTimeField(
        default=timezone.now,
    )
    send_count = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return self.phone


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    image = models.ImageField(
        upload_to="accounts/avatars/",
        blank=True,
        validators=[validate_avatar],
    )
    description = models.TextField(
        blank=True,
        max_length=2000,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            self.user.get_full_name().strip()
            or self.user.username
        )


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
    )
    recipient_name = models.CharField(max_length=150)
    recipient_phone = models.CharField(
        max_length=11,
        validators=[phone_validator],
    )
    province = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    street_address = models.CharField(max_length=500)
    building_number = models.CharField(max_length=20)
    unit = models.CharField(max_length=20, blank=True)
    postal_code = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                r"\A[0-9]{10}\Z",
                "کد پستی باید ۱۰ رقم باشد.",
            ),
        ],
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True),
                name="accounts_one_default_address",
            ),
        ]

    def clean(self):
        super().clean()

        required = [
            "recipient_name",
            "province",
            "city",
            "street_address",
            "building_number",
        ]
        errors = {}

        for name in required:
            value = getattr(self, name, "")
            if not value or not value.strip():
                errors[name] = "این فیلد الزامی است."

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.recipient_name} - {self.city}"