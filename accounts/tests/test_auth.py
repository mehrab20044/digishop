from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import AuthSession, OTPChallenge

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
    with patch("accounts.services.auth_service.send_otp") as sender:
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
    assert not AuthSession.objects.exists()


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
    identity = User.objects.get(phone=PHONE)

    assert data["access"]
    assert data["refresh"]
    assert data["is_new_user"] is True
    assert data["user"]["phone"] == PHONE
    assert identity.is_staff is False
    assert identity.is_superuser is False
    assert not identity.has_usable_password()
    assert "password" not in data["user"]

    api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {data['access']}"
    )
    response = api.get(BASE + "me/")
    assert response.status_code == 200
    assert response.data["id"] == identity.pk


def test_existing_user_can_login_without_duplicate_account(api, sms):
    first = login(api, sms)

    OTPChallenge.objects.filter(phone=PHONE).update(
        last_sent_at=timezone.now() - timedelta(seconds=61)
    )
    second = login(api, sms)

    assert second["is_new_user"] is False
    assert first["user"]["id"] == second["user"]["id"]
    assert User.objects.count() == 1
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
        "accounts.services.auth_service.secrets.randbelow",
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
    assert user.phone == PHONE


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

def test_refresh_url_uses_accounts_view():
    from django.urls import resolve

    from accounts.api.v1.views import RefreshView

    match = resolve(BASE + "token/refresh/")
    assert match.func.view_class is RefreshView


def test_refresh_applies_ip_throttle(api):
    from accounts.throttles import AuthIPThrottle

    with (
        patch.object(
            AuthIPThrottle,
            "allow_request",
            return_value=False,
        ),
        patch.object(
            AuthIPThrottle,
            "wait",
            return_value=7,
        ),
    ):
        response = api.post(
            BASE + "token/refresh/",
            {"refresh": "invalid-token"},
            format="json",
        )

    assert response.status_code == 429
    assert response["Retry-After"] == "7"


def test_logout_immediately_rejects_previous_access(api, sms):
    data = login(api, sms)
    api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {data['access']}",
    )

    response = api.post(
        BASE + "logout/",
        {"refresh": data["refresh"]},
        format="json",
    )

    assert response.status_code == 204
    assert api.get(BASE + "me/").status_code == 401


def test_customer_phone_is_verified_after_successful_otp(api, sms):
    data = login(api, sms)
    user = User.objects.get(pk=data["user"]["id"])

    assert user.phone == PHONE
    assert user.phone_verified_at is not None
    assert AuthSession.objects.filter(user=user).count() == 1


def test_inactive_user_cannot_refresh(api, sms):
    data = login(api, sms)
    User.objects.filter(pk=data["user"]["id"]).update(is_active=False)

    response = api.post(
        BASE + "token/refresh/",
        {"refresh": data["refresh"]},
        format="json",
    )

    assert response.status_code == 401


def test_expired_session_rejects_access_and_refresh(api, sms):
    data = login(api, sms)
    AuthSession.objects.update(
        expires_at=timezone.now() - timedelta(seconds=1),
    )

    api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {data['access']}",
    )
    assert api.get(BASE + "me/").status_code == 401

    api.credentials()
    response = api.post(
        BASE + "token/refresh/",
        {"refresh": data["refresh"]},
        format="json",
    )
    assert response.status_code == 401


def test_logout_all_revokes_both_logins(api, sms):
    first = login(api, sms)

    OTPChallenge.objects.filter(phone=PHONE).update(
        last_sent_at=timezone.now() - timedelta(seconds=61),
    )
    second = login(api, sms)

    api.credentials(
        HTTP_AUTHORIZATION=f"Bearer {first['access']}",
    )
    assert api.post(BASE + "logout-all/").status_code == 204

    for data in (first, second):
        api.credentials(
            HTTP_AUTHORIZATION=f"Bearer {data['access']}",
        )
        assert api.get(BASE + "me/").status_code == 401

        api.credentials()
        response = api.post(
            BASE + "token/refresh/",
            {"refresh": data["refresh"]},
            format="json",
        )
        assert response.status_code == 401


def test_management_request_does_not_register_unknown_user(api, sms):
    response = api.post(
        BASE + "management/otp/request/",
        {"phone": PHONE},
        format="json",
    )

    assert response.status_code == 200
    sms.assert_not_called()
    assert not User.objects.exists()
    assert not OTPChallenge.objects.exists()


def test_customer_cannot_login_through_management(api, sms):
    login(api, sms)
    sms.reset_mock()

    response = api.post(
        BASE + "management/otp/request/",
        {"phone": PHONE},
        format="json",
    )

    assert response.status_code == 200
    sms.assert_not_called()

    response = api.post(
        BASE + "management/otp/verify/",
        {"phone": PHONE, "code": "123456"},
        format="json",
    )
    assert response.status_code == 400


def test_customer_refresh_cannot_use_management_refresh_route(api, sms):
    data = login(api, sms)

    response = api.post(
        BASE + "management/token/refresh/",
        {"refresh": data["refresh"]},
        format="json",
    )

    assert response.status_code == 401


def test_staff_can_login_through_management(api, sms):
    user = User.objects.create_user(
        phone=PHONE,
        is_staff=True,
    )

    requested = api.post(
        BASE + "management/otp/request/",
        {"phone": PHONE},
        format="json",
    )
    assert requested.status_code == 200
    code = sms.call_args.args[1]

    verified = api.post(
        BASE + "management/otp/verify/",
        {"phone": PHONE, "code": code},
        format="json",
    )
    assert verified.status_code == 200
    assert verified.data["is_new_user"] is False
    assert verified.data["user"]["id"] == user.pk

    session = AuthSession.objects.get(user=user)
    assert session.purpose == "management"

    refreshed = api.post(
        BASE + "management/token/refresh/",
        {"refresh": verified.data["refresh"]},
        format="json",
    )
    assert refreshed.status_code == 200


def test_removing_staff_blocks_management_refresh(api, sms):
    user = User.objects.create_user(phone=PHONE, is_staff=True)

    api.post(
        BASE + "management/otp/request/",
        {"phone": PHONE},
        format="json",
    )
    code = sms.call_args.args[1]

    verified = api.post(
        BASE + "management/otp/verify/",
        {"phone": PHONE, "code": code},
        format="json",
    )
    assert verified.status_code == 200

    User.objects.filter(pk=user.pk).update(is_staff=False)

    response = api.post(
        BASE + "management/token/refresh/",
        {"refresh": verified.data["refresh"]},
        format="json",
    )
    assert response.status_code == 401
