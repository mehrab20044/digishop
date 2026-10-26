from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from threading import Barrier
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import (
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.test import (
    APIClient,
    APIRequestFactory,
    force_authenticate,
)
from rest_framework.views import APIView

from accounts.models import (
    Address,
    OTPChallenge,
    Profile,
)
from accounts.permissions import HasCompleteProfile
from accounts.services.auth_service import request_otp, verify_otp
from accounts.services.profile_service import (
    create_address,
    get_profile_status,
)

User = get_user_model()
BASE = "/api/v1/auth/"
pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def customer():
    user = User.objects.create_user(
        phone="09123456789",
        phone_verified_at=timezone.now(),
        password=None,
    )
    Profile.objects.create(user=user)
    return user


@pytest.fixture
def api(customer):
    client = APIClient()
    client.force_authenticate(customer)
    return client


@pytest.fixture
def address_data():
    return {
        "recipient_name": "Mehrab Mohammadi",
        "recipient_phone": "09123456789",
        "province": "Qazvin",
        "city": "Mohammadiyeh",
        "street_address": "Main street",
        "building_number": "12",
        "postal_code": "1234567890",
    }


def complete(api, address_data):
    return api.post(
        BASE + "me/complete/",
        {
            "first_name": "Mehrab",
            "last_name": "Mohammadi",
            "address": address_data,
        },
        format="json",
    )


def test_signup_creates_empty_profile_and_reports_missing_fields():
    with patch("accounts.services.auth_service.send_otp") as sender:
        request_otp("09999999999")
        code = sender.call_args.args[1]

        client = APIClient()
        response = client.post(
            BASE + "otp/verify/",
            {
                "phone": "09999999999",
                "code": code,
            },
            format="json",
        )

    assert response.status_code == 200
    data = response.data["user"]

    assert data["profile_completed"] is False
    assert set(data["missing_fields"]) == {
        "first_name",
        "last_name",
        "address",
    }
    assert Profile.objects.filter(
        user_id=data["id"],
    ).exists()

    client.credentials(
        HTTP_AUTHORIZATION=(
            "Bearer " + response.data["access"]
        ),
    )
    assert client.get(BASE + "me/").status_code == 200

    refreshed = client.post(
        BASE + "token/refresh/",
        {"refresh": response.data["refresh"]},
        format="json",
    )
    assert refreshed.status_code == 200


def test_incomplete_user_can_view_and_edit_own_profile(
    api,
    customer,
):
    response = api.patch(
        BASE + "me/",
        {
            "first_name": "Mehrab",
            "description": "Backend engineer",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["profile_completed"] is False
    assert response.data["description"] == "Backend engineer"

    customer.refresh_from_db()
    customer.profile.refresh_from_db()

    assert customer.first_name == "Mehrab"
    assert customer.profile.description == "Backend engineer"
    assert "phone" in response.data


def test_completion_is_atomic_when_no_address(api, customer):
    response = api.post(
        BASE + "me/complete/",
        {
            "first_name": "Mehrab",
            "last_name": "Mohammadi",
        },
        format="json",
    )

    assert response.status_code == 400
    customer.refresh_from_db()
    assert customer.first_name == ""
    assert customer.last_name == ""


def test_complete_profile_and_address_in_one_request(
    api,
    customer,
    address_data,
):
    response = complete(api, address_data)

    assert response.status_code == 200, response.data
    assert response.data["profile_completed"] is True
    assert response.data["missing_fields"] == []
    assert len(response.data["addresses"]) == 1
    assert response.data["addresses"][0]["is_default"] is True
    assert Address.objects.get().user_id == customer.pk


def test_complete_with_previously_saved_address(
    api,
    customer,
    address_data,
):
    create_address(customer, address_data)

    response = api.post(
        BASE + "me/complete/",
        {
            "first_name": "Mehrab",
            "last_name": "Mohammadi",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["profile_completed"] is True
    assert Address.objects.count() == 1


@pytest.mark.parametrize(
    "field",
    ["first_name", "last_name"],
)
def test_blank_required_names_rejected(
    api,
    address_data,
    field,
):
    payload = {
        "first_name": "Mehrab",
        "last_name": "Mohammadi",
        "address": address_data,
    }
    payload[field] = "   "

    response = api.post(
        BASE + "me/complete/",
        payload,
        format="json",
    )
    assert response.status_code == 400
    assert not Address.objects.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("recipient_name", ""),
        ("recipient_phone", "123"),
        ("province", " "),
        ("city", ""),
        ("street_address", ""),
        ("building_number", ""),
        ("postal_code", "123"),
        ("postal_code", "abcdefghij"),
    ],
)
def test_invalid_address_rejected_atomically(
    api,
    customer,
    address_data,
    field,
    value,
):
    address_data[field] = value

    assert complete(api, address_data).status_code == 400
    assert not Address.objects.exists()

    customer.refresh_from_db()
    assert customer.first_name == ""


def test_address_normalizes_phone_and_postal_digits(
    api,
    address_data,
):
    address_data.update(
        recipient_phone="+989123456789",
        postal_code="۱۲۳۴۵۶۷۸۹۰",
    )

    response = api.post(
        BASE + "addresses/",
        address_data,
        format="json",
    )

    assert response.status_code == 201, response.data
    assert response.data["recipient_phone"] == "09123456789"
    assert response.data["postal_code"] == "1234567890"


def test_defaults_can_switch_in_both_directions(
    api,
    address_data,
):
    first = api.post(
        BASE + "addresses/",
        address_data,
        format="json",
    ).data
    second = api.post(
        BASE + "addresses/",
        address_data,
        format="json",
    ).data

    assert first["is_default"] is True
    assert second["is_default"] is False

    for pk in [second["id"], first["id"]]:
        response = api.patch(
            BASE + f"addresses/{pk}/",
            {"is_default": True},
            format="json",
        )
        assert response.status_code == 200, response.data
        assert Address.objects.filter(
            is_default=True,
        ).count() == 1
        assert Address.objects.get(is_default=True).pk == pk


def test_database_prevents_duplicate_defaults(
    customer,
    address_data,
):
    create_address(customer, address_data)

    with pytest.raises(IntegrityError), transaction.atomic():
        Address.objects.create(
            user=customer,
            is_default=True,
            **address_data,
        )


def test_deleting_default_promotes_remaining_address(
    api,
    address_data,
):
    first = api.post(
        BASE + "addresses/",
        address_data,
        format="json",
    ).data
    second = api.post(
        BASE + "addresses/",
        address_data,
        format="json",
    ).data

    response = api.delete(
        BASE + f"addresses/{first['id']}/",
    )
    assert response.status_code == 204
    assert Address.objects.get(
        pk=second["id"],
    ).is_default is True


def test_removing_last_address_reblocks_profile(
    api,
    customer,
    address_data,
):
    assert complete(api, address_data).status_code == 200

    address = Address.objects.get()
    response = api.delete(
        BASE + f"addresses/{address.pk}/",
    )
    assert response.status_code == 204

    state = api.get(BASE + "me/").data
    assert state["profile_completed"] is False
    assert state["missing_fields"] == ["address"]


def test_clearing_required_name_reblocks_profile(
    api,
    address_data,
):
    assert complete(api, address_data).status_code == 200

    response = api.patch(
        BASE + "me/",
        {"first_name": ""},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["profile_completed"] is False
    assert "first_name" in response.data["missing_fields"]


def test_completion_flag_cannot_be_forged(api):
    response = api.patch(
        BASE + "me/",
        {
            "profile_completed": True,
            "missing_fields": [],
            "phone": "09999999999",
            "is_staff": True,
            "username": "hacked",
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["profile_completed"] is False
    assert response.data["phone"] == "09123456789"
    assert response.data["phone"] == "09123456789"
    assert not User.objects.get(
        phone="09123456789",
    ).is_staff


@pytest.mark.parametrize(
    "method",
    ["get", "patch", "delete"],
)
def test_cannot_access_another_users_address(
    api,
    address_data,
    method,
):
    other = User.objects.create_user(phone="09987654321")
    address = create_address(other, address_data)

    response = getattr(api, method)(
        BASE + f"addresses/{address.pk}/",
    )

    assert response.status_code == 404
    assert Address.objects.filter(pk=address.pk).exists()


def test_address_list_and_profile_hide_other_users_addresses(
    api,
    address_data,
):
    other = User.objects.create_user(phone="09987654321")
    create_address(other, address_data)

    response = api.get(BASE + "addresses/")
    results = (
        response.data.get("results", [])
        if isinstance(response.data, dict)
        else response.data
    )

    assert results == []
    assert api.get(BASE + "me/").data["addresses"] == []


def test_create_address_ignores_forged_owner(
    api,
    customer,
    address_data,
):
    other = User.objects.create_user(phone="09987654321")

    response = api.post(
        BASE + "addresses/",
        {**address_data, "user": other.pk},
        format="json",
    )

    assert response.status_code == 201
    assert Address.objects.get().user_id == customer.pk


@pytest.mark.parametrize(
    "path,method",
    [
        ("me/", "get"),
        ("me/", "patch"),
        ("me/complete/", "post"),
        ("addresses/", "get"),
        ("addresses/", "post"),
        ("addresses/1/", "delete"),
    ],
)
def test_private_endpoints_require_authentication(
    path,
    method,
):
    client = APIClient()
    response = getattr(client, method)(BASE + path)
    assert response.status_code == 401


def test_avatar_upload_and_optional_clear(
    api,
    tmp_path,
    settings,
):
    settings.MEDIA_ROOT = tmp_path

    stream = BytesIO()
    Image.new("RGB", (8, 8), "green").save(
        stream,
        format="PNG",
    )
    image = SimpleUploadedFile(
        "avatar.png",
        stream.getvalue(),
        content_type="image/png",
    )

    response = api.patch(
        BASE + "me/",
        {"image": image},
        format="multipart",
    )
    assert response.status_code == 200, response.data
    assert response.data["image"]

    response = api.patch(
        BASE + "me/",
        {"image": None},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["image"] is None


def test_invalid_avatar_is_rejected(api):
    image = SimpleUploadedFile(
        "fake.png",
        b"not an image",
        content_type="image/png",
    )

    response = api.patch(
        BASE + "me/",
        {"image": image},
        format="multipart",
    )
    assert response.status_code == 400


def test_permission_blocks_incomplete_user_and_allows_completed_user(
    api,
    customer,
    address_data,
):
    class ProtectedAction(APIView):
        permission_classes = [
            IsAuthenticated,
            HasCompleteProfile,
        ]

        def post(self, request):
            return Response({"ok": True})

    factory = APIRequestFactory()

    request = factory.post("/protected-action/")
    force_authenticate(request, customer)
    assert ProtectedAction.as_view()(request).status_code == 403

    assert complete(api, address_data).status_code == 200
    customer.refresh_from_db()

    request = factory.post("/protected-action/")
    force_authenticate(request, customer)
    assert ProtectedAction.as_view()(request).status_code == 200


def test_invalid_orm_address_does_not_mark_profile_complete(
    customer,
    address_data,
):
    customer.first_name = "Mehrab"
    customer.last_name = "Mohammadi"
    customer.save()

    Address.objects.create(
        user=customer,
        **{**address_data, "city": "   "},
    )

    assert get_profile_status(
        customer,
    )["profile_completed"] is False


def test_swagger_documents_verified_login_response(api):
    response = api.get(
        "/schema/",
        HTTP_ACCEPT="application/vnd.oai.openapi+json",
    )
    assert response.status_code == 200

    operation = response.data["paths"][
        BASE + "otp/verify/"
    ]["post"]
    ref = operation["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["$ref"]

    assert ref.endswith("/OTPVerifyResponse")




@pytest.mark.django_db(transaction=True)
def test_concurrent_signup_consumes_code_only_once():
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row-level locks")

    with patch("accounts.services.auth_service.send_otp") as sender:
        request_otp("09999999999")
        code = sender.call_args.args[1]

    barrier = Barrier(2)

    def worker():
        from rest_framework.exceptions import ValidationError

        close_old_connections()

        try:
            barrier.wait(timeout=10)

            try:
                verify_otp("09999999999", code)
                return "ok"
            except ValidationError:
                return "rejected"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: worker(), range(2)),
        )

    assert sorted(results) == ["ok", "rejected"]

    identity = User.objects.get(
        phone="09999999999",
    )
    assert Profile.objects.filter(
        user_id=identity.pk,
    ).count() == 1


def test_signup_profile_failure_rolls_back_account_and_code_consumption():
    with patch("accounts.services.auth_service.send_otp") as sender:
        request_otp("09999999999")
        code = sender.call_args.args[1]

    with patch(
        "accounts.services.auth_service.Profile.objects.get_or_create",
        side_effect=RuntimeError("database failure"),
    ):
        with pytest.raises(RuntimeError):
            verify_otp("09999999999", code)

    assert not User.objects.filter(
        phone="09999999999",
    ).exists()
    assert not User.objects.exists()
    assert OTPChallenge.objects.get(
        phone="09999999999",
    ).consumed_at is None


def test_login_reports_existing_completed_profile(
    api,
    customer,
    address_data,
):
    assert complete(api, address_data).status_code == 200

    with patch("accounts.services.auth_service.send_otp") as sender:
        request_otp("09123456789")
        code = sender.call_args.args[1]

    response = APIClient().post(
        BASE + "otp/verify/",
        {
            "phone": "09123456789",
            "code": code,
        },
        format="json",
    )

    assert response.status_code == 200
    assert response.data["is_new_user"] is False
    assert response.data["user"]["profile_completed"] is True
    assert Profile.objects.filter(user=customer).count() == 1


def test_admin_can_switch_default_address(
    admin_client,
    customer,
    address_data,
):
    create_address(customer, address_data)
    replacement = create_address(customer, address_data)

    response = admin_client.post(
        reverse("admin:accounts_address_changelist"),
        {
            "action": "make_default",
            "_selected_action": [
                str(replacement.pk),
            ],
        },
    )

    assert response.status_code == 302
    assert Address.objects.get(
        is_default=True,
    ).pk == replacement.pk


@pytest.mark.django_db(transaction=True)
def test_concurrent_address_creation_keeps_one_default(
    address_data,
):
    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row-level locks")

    user = User.objects.create_user(
        phone="09900000001",
    )
    barrier = Barrier(2)

    def worker():
        close_old_connections()

        try:
            current = User.objects.get(pk=user.pk)
            barrier.wait(timeout=10)

            return create_address(
                current,
                {
                    **address_data,
                    "is_default": True,
                },
            ).pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(
            pool.map(lambda _: worker(), range(2)),
        )

    assert len(set(ids)) == 2
    assert Address.objects.filter(user=user).count() == 2
    assert Address.objects.filter(
        user=user,
        is_default=True,
    ).count() == 1

def test_initial_migration_defines_custom_user():
    from django.db.migrations.loader import MigrationLoader

    state = MigrationLoader(connection).project_state(
        [("accounts", "0001_initial")],
    )
    historical_user = state.apps.get_model("accounts", "User")

    assert historical_user._meta.get_field("phone").unique is True
    assert historical_user._meta.get_field("phone_verified_at")
