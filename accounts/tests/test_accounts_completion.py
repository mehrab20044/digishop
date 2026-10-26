from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from accounts.models import Address, AuthSession, Profile
from accounts.permissions import HasCompleteProfile
from accounts.services.auth_service import request_otp, verify_otp

User = get_user_model()

pytestmark = pytest.mark.django_db

AUTH = "/api/v1/auth/"
STAFF = "/api/v1/owner/staff/"


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


def login(user, purpose="customer"):
    with patch("accounts.services.auth_service.send_otp") as sender:
        request_otp(user.phone, purpose=purpose)
        code = sender.call_args.args[1]
        tokens = verify_otp(
            user.phone,
            code,
            purpose=purpose,
        )

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {tokens['access']}",
    )
    return client, tokens


def grant(user, app, codename):
    permission = Permission.objects.get(
        content_type__app_label=app,
        codename=codename,
    )
    user.user_permissions.add(permission)
    return permission


def address_payload(**changes):
    return {
        "recipient_name": "Test Recipient",
        "recipient_phone": "09123456789",
        "province": "قزوین",
        "city": "محمدیه",
        "street_address": "خیابان آزمایش، ساختمان یک",
        "building_number": "12",
        "unit": "2",
        "postal_code": "1234567890",
        "is_default": False,
        **changes,
    }


@pytest.fixture
def owner():
    return User.objects.create_superuser(
        phone="09310000001",
        password="StrongTestPassword123!",
    )


@pytest.fixture
def manager():
    user = User.objects.create_user(
        phone="09310000002",
        is_staff=True,
    )

    for action in ("view", "add", "change"):
        grant(user, "accounts", f"{action}_user")

    grant(user, "products", "view_category")
    return user


def test_complete_profile_permission_returns_true():
    user = User.objects.create_user(
        phone="09310000003",
        first_name="Test",
        last_name="User",
        phone_verified_at=timezone.now(),
    )
    Address.objects.create(
        user=user,
        **address_payload(is_default=True),
    )

    request = APIRequestFactory().get("/")
    request.user = user

    assert HasCompleteProfile().has_permission(request, None) is True


def test_customer_cannot_open_staff_api():
    user = User.objects.create_user(phone="09310000004")
    client, _ = login(user)

    assert client.get(STAFF).status_code == 403


def test_owner_customer_session_cannot_manage_staff(owner):
    client, _ = login(owner)

    assert client.get(STAFF).status_code == 403


def test_staff_without_user_permission_cannot_list():
    user = User.objects.create_user(
        phone="09310000005",
        is_staff=True,
    )
    client, _ = login(user, "management")

    assert client.get(STAFF).status_code == 403


def test_owner_can_create_staff_with_unusable_password(owner):
    client, _ = login(owner, "management")

    response = client.post(
        STAFF,
        {
            "phone": "09310000006",
            "first_name": "New",
            "last_name": "Staff",
            "permissions": ["products.view_category"],
        },
        format="json",
    )

    assert response.status_code == 201, response.data

    user = User.objects.get(phone="09310000006")
    assert user.is_staff is True
    assert user.is_superuser is False
    assert user.has_usable_password() is False
    assert user.has_perm("products.view_category") is True


def test_existing_customer_is_not_silently_promoted(owner):
    customer = User.objects.create_user(phone="09310000007")
    client, _ = login(owner, "management")

    response = client.post(
        STAFF,
        {"phone": customer.phone},
        format="json",
    )

    assert response.status_code == 400
    customer.refresh_from_db()
    assert customer.is_staff is False


def test_manager_can_delegate_own_business_permission(manager):
    client, _ = login(manager, "management")

    response = client.post(
        STAFF,
        {
            "phone": "09310000008",
            "permissions": ["products.view_category"],
        },
        format="json",
    )

    assert response.status_code == 201, response.data


def test_manager_cannot_delegate_permission_they_do_not_have(manager):
    client, _ = login(manager, "management")

    response = client.post(
        STAFF,
        {
            "phone": "09310000009",
            "permissions": ["products.change_category"],
        },
        format="json",
    )

    assert response.status_code == 400
    assert not User.objects.filter(phone="09310000009").exists()


def test_group_permission_is_included_in_manager_limit(manager):
    permission = Permission.objects.get(
        content_type__app_label="products",
        codename="change_category",
    )
    group = Group.objects.create(name="Category editors")
    group.permissions.add(permission)
    manager.groups.add(group)

    client, _ = login(manager, "management")

    response = client.post(
        STAFF,
        {
            "phone": "09310000010",
            "permissions": ["products.change_category"],
        },
        format="json",
    )

    assert response.status_code == 201, response.data


def test_privilege_fields_are_rejected(owner):
    client, _ = login(owner, "management")

    response = client.post(
        STAFF,
        {
            "phone": "09310000011",
            "is_superuser": True,
            "groups": [],
        },
        format="json",
    )

    assert response.status_code == 400
    assert not User.objects.filter(phone="09310000011").exists()


def test_staff_api_cannot_delegate_user_management(owner):
    client, _ = login(owner, "management")

    response = client.post(
        STAFF,
        {
            "phone": "09310000012",
            "permissions": ["accounts.change_user"],
        },
        format="json",
    )

    assert response.status_code == 400


def test_owner_and_self_are_protected(owner, manager):
    manager_client, _ = login(manager, "management")

    response = manager_client.patch(
        STAFF + f"{owner.pk}/",
        {"is_active": False},
        format="json",
    )
    assert response.status_code == 403

    response = manager_client.patch(
        STAFF + f"{manager.pk}/",
        {"is_active": False},
        format="json",
    )
    assert response.status_code == 403


def test_manager_cannot_modify_stronger_staff(manager):
    stronger = User.objects.create_user(
        phone="09310000013",
        is_staff=True,
    )
    grant(stronger, "products", "change_category")

    client, _ = login(manager, "management")

    response = client.patch(
        STAFF + f"{stronger.pk}/",
        {"first_name": "Changed"},
        format="json",
    )

    assert response.status_code == 403
    stronger.refresh_from_db()
    assert stronger.first_name == ""


def test_manager_cannot_modify_group_managed_staff(manager):
    target = User.objects.create_user(
        phone="09310000014",
        is_staff=True,
    )
    group = Group.objects.create(name="Managed group")
    target.groups.add(group)

    client, _ = login(manager, "management")

    response = client.patch(
        STAFF + f"{target.pk}/",
        {"first_name": "Changed"},
        format="json",
    )

    assert response.status_code == 403


def test_staff_update_revokes_management_session(owner):
    target = User.objects.create_user(
        phone="09310000015",
        is_staff=True,
    )
    target_client, _ = login(target, "management")
    owner_client, _ = login(owner, "management")

    response = owner_client.patch(
        STAFF + f"{target.pk}/",
        {
            "first_name": "Updated",
            "permissions": ["products.view_category"],
        },
        format="json",
    )

    assert response.status_code == 200, response.data
    assert target_client.get("/api/v1/owner/").status_code == 401


def test_profile_patch_cannot_change_privileges():
    user = User.objects.create_user(phone="09310000016")
    client, _ = login(user)

    response = client.patch(
        AUTH + "me/",
        {
            "first_name": "Updated",
            "is_staff": True,
            "is_superuser": True,
            "groups": [],
            "user_permissions": [],
        },
        format="json",
    )

    assert response.status_code in (200, 400)

    user.refresh_from_db()
    assert user.is_staff is False
    assert user.is_superuser is False
    assert not user.groups.exists()
    assert not user.user_permissions.exists()


def test_customer_can_save_profile_and_clear_image():
    user = User.objects.create_user(phone="09310000017")
    Profile.objects.create(
        user=user,
        image="accounts/avatars/old.png",
    )
    client, _ = login(user)

    response = client.patch(
        AUTH + "me/",
        {
            "first_name": "Mehrab",
            "last_name": "Mohammadi",
            "email": "test@example.com",
            "description": "Profile test",
            "image": None,
        },
        format="json",
    )

    assert response.status_code == 200, response.data

    user.refresh_from_db()
    user.profile.refresh_from_db()

    assert user.first_name == "Mehrab"
    assert user.profile.description == "Profile test"
    assert not user.profile.image


def test_address_default_switch_and_delete():
    user = User.objects.create_user(phone="09310000018")
    client, _ = login(user)

    first = client.post(
        AUTH + "addresses/",
        address_payload(),
        format="json",
    )
    assert first.status_code == 201, first.data
    first_id = first.data["id"]

    second = client.post(
        AUTH + "addresses/",
        address_payload(
            street_address="آدرس دوم",
            is_default=True,
        ),
        format="json",
    )
    assert second.status_code == 201, second.data
    second_id = second.data["id"]

    assert Address.objects.filter(
        user=user,
        is_default=True,
    ).count() == 1

    assert Address.objects.get(pk=second_id).is_default is True

    response = client.delete(
        AUTH + f"addresses/{second_id}/",
    )

    assert response.status_code == 204
    assert Address.objects.get(pk=first_id).is_default is True


def test_customer_cannot_modify_another_customers_address():
    first_user = User.objects.create_user(phone="09310000019")
    second_user = User.objects.create_user(phone="09310000020")

    address = Address.objects.create(
        user=second_user,
        **address_payload(is_default=True),
    )
    client, _ = login(first_user)

    response = client.patch(
        AUTH + f"addresses/{address.pk}/",
        {"city": "Changed"},
        format="json",
    )
    assert response.status_code == 404

    response = client.delete(
        AUTH + f"addresses/{address.pk}/",
    )
    assert response.status_code == 404

    address.refresh_from_db()
    assert address.city == "محمدیه"


def test_logout_all_invalidates_customer_and_management_sessions():
    user = User.objects.create_user(
        phone="09310000021",
        is_staff=True,
    )

    customer_client, _ = login(user, "customer")
    management_client, _ = login(user, "management")

    response = customer_client.post(AUTH + "logout-all/")

    assert response.status_code == 204
    assert customer_client.get(AUTH + "me/").status_code == 401
    assert management_client.get("/api/v1/owner/").status_code == 401
    assert not AuthSession.objects.filter(
        user=user,
        revoked_at__isnull=True,
    ).exists()