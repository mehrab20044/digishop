import secrets
from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from math import ceil
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import (
    AuthenticationFailed,
    Throttled,
    ValidationError,
)
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import AuthSession, OTPChallenge, Profile
from accounts.sms import send_otp

User = get_user_model()

CUSTOMER = OTPChallenge.Purpose.CUSTOMER
MANAGEMENT = OTPChallenge.Purpose.MANAGEMENT


def _check_purpose(purpose):
    if purpose not in OTPChallenge.Purpose.values:
        raise ValueError("نوع درخواست احراز هویت معتبر نیست.")


def _management_user_exists(phone):
    return User.objects.filter(
        phone=phone,
        is_active=True,
        is_staff=True,
    ).exists()


def request_otp(phone, *, purpose=CUSTOMER):
    _check_purpose(purpose)

    # پاسخ API برای شماره ناشناخته هم یکسان است.
    # این مسیر هیچ حساب مدیریتی ایجاد نمی‌کند.
    if purpose == MANAGEMENT and not _management_user_exists(phone):
        return

    code = f"{secrets.randbelow(1_000_000):06d}"
    code_hash = make_password(code)
    now = timezone.now()

    with transaction.atomic():
        OTPChallenge.objects.get_or_create(
            phone=phone,
            purpose=purpose,
            defaults={
                "expires_at": now,
                "last_sent_at": now - timedelta(days=1),
            },
        )

        challenge = OTPChallenge.objects.select_for_update().get(
            phone=phone,
            purpose=purpose,
        )
        now = timezone.now()

        remaining = (
            settings.OTP_RESEND_SECONDS
            - (now - challenge.last_sent_at).total_seconds()
        )

        if remaining > 0:
            raise Throttled(
                wait=max(1, ceil(remaining)),
                detail="برای ارسال مجدد کمی صبر کنید.",
            )

        window = timedelta(seconds=settings.OTP_SEND_WINDOW_SECONDS)

        if now - challenge.send_window_started_at >= window:
            challenge.send_window_started_at = now
            challenge.send_count = 0

        if challenge.send_count >= settings.OTP_MAX_SENDS_PER_WINDOW:
            remaining = (
                challenge.send_window_started_at + window - now
            ).total_seconds()

            raise Throttled(
                wait=max(1, ceil(remaining)),
                detail="تعداد درخواست کد بیش از حد مجاز است.",
            )

        challenge.code_hash = code_hash
        challenge.expires_at = now + timedelta(
            seconds=settings.OTP_TTL_SECONDS,
        )
        challenge.last_sent_at = now
        challenge.failed_attempts = 0
        challenge.consumed_at = None
        challenge.send_count += 1
        challenge.save()
        challenge_id = challenge.pk

    # ارتباط شبکه‌ای بیرون از تراکنش و قفل دیتابیس است.
    try:
        send_otp(phone, code)
    except Exception:
        # فقط همین کد ناموفق را باطل می‌کنیم؛ کد جدیدتر دست نمی‌خورد.
        # محدودیت ارسال هم با شکست سرویس پیامک صفر نمی‌شود.
        OTPChallenge.objects.filter(
            pk=challenge_id,
            code_hash=code_hash,
        ).update(
            code_hash="",
            consumed_at=timezone.now(),
        )
        raise


def _issue_tokens(user, purpose):
    refresh = RefreshToken.for_user(user)

    session = AuthSession.objects.create(
        user=user,
        purpose=purpose,
        refresh_jti=refresh[api_settings.JTI_CLAIM],
        expires_at=datetime.fromtimestamp(
            refresh["exp"],
            tz=datetime_timezone.utc,
        ),
    )

    refresh["sid"] = str(session.pk)
    refresh["purpose"] = purpose

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def verify_otp(phone, code, *, purpose=CUSTOMER):
    _check_purpose(purpose)

    result = None
    inactive = False

    with transaction.atomic():
        challenge = (
            OTPChallenge.objects.select_for_update()
            .filter(phone=phone, purpose=purpose)
            .first()
        )
        now = timezone.now()

        usable = (
            challenge is not None
            and bool(challenge.code_hash)
            and challenge.consumed_at is None
            and challenge.expires_at > now
            and challenge.failed_attempts < settings.OTP_MAX_FAILED_ATTEMPTS
        )

        if usable:
            if not check_password(code, challenge.code_hash):
                challenge.failed_attempts += 1
                challenge.save(update_fields=["failed_attempts"])
            else:
                user = (
                    User.objects.select_for_update()
                    .filter(phone=phone)
                    .first()
                )
                is_new_user = user is None

                if purpose == CUSTOMER and user is None:
                    user = User.objects.create_user(phone=phone)

                allowed = (
                    user is not None
                    and (
                        purpose == CUSTOMER
                        or user.is_staff
                    )
                )

                challenge.consumed_at = now
                challenge.code_hash = ""
                challenge.save(
                    update_fields=["consumed_at", "code_hash"],
                )

                if allowed and not user.is_active:
                    inactive = True

                elif allowed:
                    user.phone_verified_at = now
                    user.last_login = now
                    user.save(
                        update_fields=["phone_verified_at", "last_login"],
                    )

                    Profile.objects.get_or_create(user=user)

                    result = {
                        "user": user,
                        "is_new_user": is_new_user,
                        **_issue_tokens(user, purpose),
                    }

    # بیرون تراکنش تا شمارنده و مصرف کد ذخیره باقی بمانند.
    if inactive:
        raise AuthenticationFailed("حساب کاربری غیرفعال است.")

    if result is None:
        raise ValidationError({
            "code": "کد نامعتبر، منقضی یا مصرف‌شده است.",
        })

    return result


def _read_refresh(value):
    try:
        return RefreshToken(value)
    except TokenError as exc:
        raise InvalidToken("توکن تمدید معتبر نیست.") from exc


def _session_id(token):
    try:
        return UUID(str(token["sid"]))
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise InvalidToken("شناسه نشست معتبر نیست.") from exc


@transaction.atomic
def refresh_session(value, *, purpose=CUSTOMER):
    _check_purpose(purpose)

    refresh = _read_refresh(value)
    session_id = _session_id(refresh)

    token_user = JWTAuthentication().get_user(refresh)
    user = User.objects.select_for_update().get(pk=token_user.pk)

    # بررسی دوباره پس از گرفتن قفل کاربر.
    JWTAuthentication().get_user(refresh)

    if not user.is_active:
        raise InvalidToken("حساب کاربری غیرفعال است.")

    if purpose == MANAGEMENT and not user.is_staff:
        raise InvalidToken("دسترسی مدیریت این حساب لغو شده است.")

    session = (
        AuthSession.objects.select_for_update()
        .filter(pk=session_id, user=user)
        .first()
    )
    now = timezone.now()

    if (
        session is None
        or session.revoked_at is not None
        or session.expires_at <= now
        or session.purpose != purpose
        or refresh.get("purpose") != purpose
        or session.refresh_jti != refresh.get(api_settings.JTI_CLAIM)
    ):
        raise InvalidToken("نشست یا توکن تمدید معتبر نیست.")

    refresh.blacklist()

    new_refresh = RefreshToken.for_user(user)
    new_refresh["sid"] = str(session.pk)
    new_refresh["purpose"] = purpose
    new_refresh["exp"] = int(session.expires_at.timestamp())

    session.refresh_jti = new_refresh[api_settings.JTI_CLAIM]
    session.save(update_fields=["refresh_jti"])

    return {
        "access": str(new_refresh.access_token),
        "refresh": str(new_refresh),
    }


@transaction.atomic
def logout_session(user, access_token, refresh_value):
    refresh = _read_refresh(refresh_value)
    session_id = _session_id(access_token)

    if (
        _session_id(refresh) != session_id
        or str(refresh.get(api_settings.USER_ID_CLAIM)) != str(user.pk)
    ):
        raise ValidationError({
            "refresh": "این توکن متعلق به نشست فعلی شما نیست.",
        })

    session = (
        AuthSession.objects.select_for_update()
        .filter(pk=session_id, user=user)
        .first()
    )

    if session is None:
        raise InvalidToken("نشست معتبر نیست.")

    session.revoked_at = timezone.now()
    session.save(update_fields=["revoked_at"])
    refresh.blacklist()


@transaction.atomic
def logout_all_sessions(user):
    # با صدور و تمدید توکن که کاربر را قفل می‌کنند هماهنگ است.
    User.objects.select_for_update().get(pk=user.pk)

    AuthSession.objects.filter(
        user=user,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())