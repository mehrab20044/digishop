import secrets
from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import (
    check_password,
    make_password,
)
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import (
    AuthenticationFailed,
    Throttled,
    ValidationError,
)
from rest_framework_simplejwt.tokens import RefreshToken

from .models import OTPChallenge, PhoneIdentity, Profile
from .sms import send_otp

User = get_user_model()


def request_otp(phone):
    now = timezone.now()

    with transaction.atomic():
        OTPChallenge.objects.get_or_create(
            phone=phone,
            defaults={
                "expires_at": now,
                "last_sent_at": now - timedelta(days=1),
            },
        )
        challenge = (
            OTPChallenge.objects.select_for_update()
            .get(phone=phone)
        )
        now = timezone.now()

        cooldown = settings.OTP_RESEND_SECONDS
        elapsed = (
            now - challenge.last_sent_at
        ).total_seconds()

        if elapsed < cooldown:
            raise Throttled(
                wait=max(
                    1,
                    int(cooldown - elapsed) + 1,
                ),
                detail="برای ارسال مجدد کمی صبر کنید.",
            )

        window = timedelta(
            seconds=settings.OTP_SEND_WINDOW_SECONDS,
        )

        if now - challenge.send_window_started_at >= window:
            challenge.send_window_started_at = now
            challenge.send_count = 0

        if (
            challenge.send_count
            >= settings.OTP_MAX_SENDS_PER_WINDOW
        ):
            remaining = (
                challenge.send_window_started_at
                + window
                - now
            ).total_seconds()

            raise Throttled(
                wait=max(1, int(remaining) + 1),
                detail="تعداد درخواست کد بیش از حد مجاز است.",
            )

        code = f"{secrets.randbelow(1_000_000):06d}"

        challenge.code_hash = make_password(code)
        challenge.expires_at = now + timedelta(
            seconds=settings.OTP_TTL_SECONDS,
        )
        challenge.last_sent_at = now
        challenge.failed_attempts = 0
        challenge.consumed_at = None
        challenge.send_count += 1
        challenge.save()

        # Current sender is for development only.
        send_otp(phone, code)


def verify_otp(phone, code):
    result = None
    failure = "کد نامعتبر، منقضی یا مصرف‌شده است."
    inactive = False

    with transaction.atomic():
        challenge = (
            OTPChallenge.objects.select_for_update()
            .filter(phone=phone)
            .first()
        )
        now = timezone.now()

        usable = (
            challenge is not None
            and bool(challenge.code_hash)
            and challenge.consumed_at is None
            and challenge.expires_at > now
            and challenge.failed_attempts
            < settings.OTP_MAX_FAILED_ATTEMPTS
        )

        if usable:
            if not check_password(
                code,
                challenge.code_hash,
            ):
                challenge.failed_attempts += 1
                challenge.save(
                    update_fields=["failed_attempts"],
                )
            else:
                identity = (
                    PhoneIdentity.objects.select_related(
                        "user",
                    )
                    .filter(phone=phone)
                    .first()
                )
                is_new_user = identity is None

                if is_new_user:
                    user = User.objects.create_user(
                        username=f"phone_{uuid4().hex}",
                        password=None,
                    )
                    PhoneIdentity.objects.create(
                        user=user,
                        phone=phone,
                    )
                else:
                    user = (
                        User.objects.select_for_update()
                        .get(pk=identity.user_id)
                    )

                challenge.consumed_at = now
                challenge.code_hash = ""
                challenge.save(
                    update_fields=[
                        "consumed_at",
                        "code_hash",
                    ],
                )

                if not user.is_active:
                    inactive = True
                else:
                    Profile.objects.get_or_create(
                        user=user,
                    )

                    refresh = RefreshToken.for_user(user)
                    result = {
                        "user": user,
                        "is_new_user": is_new_user,
                        "access": str(
                            refresh.access_token,
                        ),
                        "refresh": str(refresh),
                    }

    if inactive:
        raise AuthenticationFailed(
            "حساب کاربری غیرفعال است.",
        )

    if result is None:
        raise ValidationError({"code": failure})

    return result