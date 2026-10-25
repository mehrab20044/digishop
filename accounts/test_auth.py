from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import OTPChallenge, PhoneIdentity

User = get_user_model()

pytestmark = pytest.mark.django_db

BASE = "/api/v1/auth/"
PHONE = "09123456789"


@pytest.fixture(autouse=True)
def clean_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def sms():
    with patch("accounts.services.send_otp") as sender:
        yield sender


def request_code(api, sms, phone=PHONE):
    response = api.post(
        BASE + "otp/request/",
        {"phone": phone},
        format="json",
    )
    assert response.status_code == 200, response.data
    return sms.call_args.args[1]


def login(api, sms, phone=PHONE):
    code = request_code(api, sms, phone)
    response = api.post(
        BASE + "otp/verify/",
        {"phone": phone, "code": code},
        format="json",
    )
    assert response.status_code == 200, response.data
    return response.data


def test_request_does_not_create_user_or_return_code(api, sms):
    code = request_code(api, sms)

    challenge = OTPChallenge.objects.get(phone=PHONE)
    assert check_password(code, challenge.code_hash)
    assert challenge.code_hash != code
    assert not User.objects.exists()
    assert not PhoneIdentity.objects.exists()


@pytest.mark.parametrize(
    "phone",
    ["123", "08123456789", "091234567890", "not-a-phone"],
)
def test_invalid_phone_is_rejected(api, sms, phone):
    response = api.post(
        BASE + "otp/request/",
        {"phone": phone},
        format="json",
    )
    assert response.status_code == 400
    sms.assert_not_called()


@pytest.mark.parametrize(
    "phone",
    ["+989123456789", "00989123456789", "۰۹۱۲۳۴۵۶۷۸۹"],
)
def test_phone_is_normalized(api, sms, phone):
    request_code(api, sms, phone)
    assert OTPChallenge.objects.get().phone == PHONE
    assert sms.call_args.args[0] == PHONE


def test_signup_issues_tokens_and_creates_normal_user(api, sms):
    data = login(api, sms)
    identity = PhoneIdentity.objects.get(phone=PHONE)

    assert data["access"]
    assert data["refresh"]
    assert data["is_new_user"] is True
    assert data["user"]["phone"] == PHONE
    assert identity.user.is_staff is False
    assert identity.user.is_superuser is False
    assert not identity.user.has_usable_password()
    assert "password" not in data["user"]

    api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {data['access']}"
    )
    response = api.get(BASE + "me/")
    assert response.status_code == 200
    assert response.data["id"] == identity.user_id


def test_existing_user_can_login_without_duplicate_account(api, sms):
    first = login(api, sms)

    OTPChallenge.objects.filter(phone=PHONE).update(
        last_sent_at=timezone.now() - timedelta(seconds=61)
    )
    second = login(api, sms)

    assert second["is_new_user"] is False
    assert first["user"]["id"] == second["user"]["id"]
    assert PhoneIdentity.objects.count() == 1
    assert User.objects.count() == 1


def test_wrong_attempts_are_saved_and_correct_code_is_blocked(api, sms):
    code = request_code(api, sms)
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(5):
        response = api.post(
            BASE + "otp/verify/",
            {"phone": PHONE, "code": wrong},
            format="json",
        )
        assert response.status_code == 400

    assert OTPChallenge.objects.get().failed_attempts == 5

    response = api.post(
        BASE + "otp/verify/",
        {"phone": PHONE, "code": code},
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.exists()


def test_expired_code_is_rejected(api, sms):
    code = request_code(api, sms)
    OTPChallenge.objects.update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )

    response = api.post(
        BASE + "otp/verify/",
        {"phone": PHONE, "code": code},
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.exists()


def test_code_cannot_be_reused(api, sms):
    code = request_code(api, sms)
    payload = {"phone": PHONE, "code": code}

    first = api.post(BASE + "otp/verify/", payload, format="json")
    second = api.post(BASE + "otp/verify/", payload, format="json")

    assert first.status_code == 200
    assert second.status_code == 400
    assert OTPChallenge.objects.get().code_hash == ""
    assert User.objects.count() == 1


def test_resend_cooldown(api, sms):
    request_code(api, sms)
    response = api.post(
        BASE + "otp/request/",
        {"phone": PHONE},
        format="json",
    )

    assert response.status_code == 429
    assert sms.call_count == 1


def test_hourly_phone_limit(api, sms):
    request_code(api, sms)
    OTPChallenge.objects.update(
        send_count=5,
        last_sent_at=timezone.now() - timedelta(seconds=61),
    )

    response = api.post(
        BASE + "otp/request/",
        {"phone": PHONE},
        format="json",
    )
    assert response.status_code == 429
    assert sms.call_count == 1


def test_resending_invalidates_previous_code(api, sms):
    sms.side_effect = None

    with patch(
        "accounts.services.secrets.randbelow",
        side_effect=[123456, 654321],
    ):
        old = request_code(api, sms)
        OTPChallenge.objects.update(
            last_sent_at=timezone.now() - timedelta(seconds=61)
        )
        new = request_code(api, sms)

    assert old != new

    rejected = api.post(
        BASE + "otp/verify/",
        {"phone": PHONE, "code": old},
        format="json",
    )
    accepted = api.post(
        BASE + "otp/verify/",
        {"phone": PHONE, "code": new},
        format="json",
    )
    assert rejected.status_code == 400
    assert accepted.status_code == 200


def test_inactive_user_cannot_login(api, sms):
    data = login(api, sms)
    User.objects.filter(pk=data["user"]["id"]).update(
        is_active=False
    )
    OTPChallenge.objects.update(
        last_sent_at=timezone.now() - timedelta(seconds=61)
    )
    code = request_code(api, sms)

    response = api.post(
        BASE + "otp/verify/",
        {"phone": PHONE, "code": code},
        format="json",
    )
    assert response.status_code == 401


def test_profile_requires_authentication(api):
    assert api.get(BASE + "me/").status_code == 401


def test_profile_cannot_change_identity_or_privileges(api, sms):
    data = login(api, sms)
    api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {data['access']}"
    )

    response = api.patch(
        BASE + "me/",
        {
            "first_name": "Mehrab",
            "phone": "09999999999",
            "is_staff": True,
            "is_superuser": True,
            "username": "changed",
        },
        format="json",
    )

    assert response.status_code == 200
    user = User.objects.get(pk=data["user"]["id"])
    assert user.first_name == "Mehrab"
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.username != "changed"
    assert user.phone_identity.phone == PHONE


def test_refresh_rotates_and_rejects_previous_token(api, sms):
    data = login(api, sms)

    response = api.post(
        BASE + "token/refresh/",
        {"refresh": data["refresh"]},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["access"]
    assert response.data["refresh"] != data["refresh"]

    reused = api.post(
        BASE + "token/refresh/",
        {"refresh": data["refresh"]},
        format="json",
    )
    assert reused.status_code == 401


def test_logout_blacklists_refresh(api, sms):
    data = login(api, sms)
    api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {data['access']}"
    )

    response = api.post(
        BASE + "logout/",
        {"refresh": data["refresh"]},
        format="json",
    )
    assert response.status_code == 204

    api.credentials()
    response = api.post(
        BASE + "token/refresh/",
        {"refresh": data["refresh"]},
        format="json",
    )
    assert response.status_code == 401


def test_logout_rejects_another_users_refresh(api, sms):
    first = login(api, sms)
    second = login(api, sms, "09987654321")

    api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {first['access']}"
    )
    response = api.post(
        BASE + "logout/",
        {"refresh": second["refresh"]},
        format="json",
    )
    assert response.status_code == 400

    api.credentials()
    response = api.post(
        BASE + "token/refresh/",
        {"refresh": second["refresh"]},
        format="json",
    )
    assert response.status_code == 200


def test_invalid_refresh_is_rejected(api):
    response = api.post(
        BASE + "token/refresh/",
        {"refresh": "invalid-token"},
        format="json",
    )
    assert response.status_code == 401