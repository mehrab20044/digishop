from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from rest_framework.test import APIClient

from accounts.services.auth_service import request_otp, verify_otp
from products.models import Category

User = get_user_model()

pytestmark = pytest.mark.django_db
BASE = "/api/v1/owner/"


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


def authenticated_client(user, purpose="management"):
    with patch("accounts.services.auth_service.send_otp") as sender:
        request_otp(user.phone, purpose=purpose)
        code = sender.call_args.args[1]
        data = verify_otp(user.phone, code, purpose=purpose)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {data['access']}",
    )
    return client


def grant(user, codename):
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="products",
            codename=codename,
        ),
    )


def test_dashboard_requires_authentication():
    assert APIClient().get(BASE).status_code == 401


def test_customer_session_cannot_open_dashboard():
    user = User.objects.create_user(phone="09111111111")
    client = authenticated_client(user, purpose="customer")

    assert client.get(BASE).status_code == 403


def test_owner_customer_session_is_not_management_session():
    owner = User.objects.create_superuser(
        phone="09111111112",
        password="StrongTestPassword123!",
    )
    client = authenticated_client(owner, purpose="customer")

    assert client.get(BASE).status_code == 403


def test_django_cookie_alone_cannot_open_dashboard():
    owner = User.objects.create_superuser(
        phone="09111111113",
        password="StrongTestPassword123!",
    )
    client = APIClient()
    client.force_login(owner)

    assert client.get(BASE).status_code == 401


def test_owner_management_session_can_open_dashboard():
    owner = User.objects.create_superuser(
        phone="09111111114",
        password="StrongTestPassword123!",
    )
    client = authenticated_client(owner)

    assert client.get(BASE).status_code == 200


def test_staff_without_permission_cannot_view_categories():
    staff = User.objects.create_user(
        phone="09111111115",
        is_staff=True,
    )
    client = authenticated_client(staff)

    assert client.get(BASE + "categories/").status_code == 403


def test_view_permission_does_not_allow_changes():
    staff = User.objects.create_user(
        phone="09111111116",
        is_staff=True,
    )
    grant(staff, "view_category")

    category = Category.objects.create(
        name="Phones",
        slug="phones",
    )
    client = authenticated_client(staff)

    assert client.get(BASE + "categories/").status_code == 200

    response = client.patch(
        BASE + f"categories/{category.pk}/edit/",
        {"name": "Changed"},
        format="json",
    )
    assert response.status_code == 403

    category.refresh_from_db()
    assert category.name == "Phones"


def test_change_permission_is_checked_on_each_request():
    staff = User.objects.create_user(
        phone="09111111117",
        is_staff=True,
    )
    grant(staff, "view_category")

    category = Category.objects.create(
        name="Phones",
        slug="phones",
    )
    client = authenticated_client(staff)

    grant(staff, "change_category")

    response = client.patch(
        BASE + f"categories/{category.pk}/edit/",
        {"name": "Updated phones"},
        format="json",
    )
    assert response.status_code == 200

    staff.user_permissions.clear()

    response = client.get(BASE + "categories/")
    assert response.status_code == 403


def test_staff_without_seo_permissions_cannot_open_seo():
    staff = User.objects.create_user(
        phone="09111111118",
        is_staff=True,
    )
    client = authenticated_client(staff)

    assert client.get(BASE + "seo/").status_code == 403