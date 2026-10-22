import pytest
from django.contrib.auth import get_user_model
from django.core import signing
from django.urls import reverse

from seo.models import SEOSettings, SEOSettingsLog


@pytest.mark.django_db
def test_non_superuser_cannot_change_seo_settings(client):
    user = get_user_model().objects.create_user(
        username="staff_tester",
        password="TestPassword123!",
        is_staff=True,
        is_superuser=False,
    )

    SEOSettings.get_settings()
    client.force_login(user)

    url = reverse("admin:seo_seosettings_change", args=[1])

    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_seo_change_requires_confirmation(client):
    user = get_user_model().objects.create_superuser(
        username="seo_admin",
        email="admin@example.com",
        password="TestPassword123!",
    )

    settings = SEOSettings.get_settings()
    client.force_login(user)

    url = reverse(
        "admin:seo_seosettings_change",
        args=[settings.pk],
    )

    # مرحله اول: درخواست تغییر وضعیت خزش
    response = client.post(
        url,
        {
            "allow_crawling": "on",
            "_save": "Save",
        },
    )

    # باید صفحه تأیید نمایش داده شود
    assert response.status_code == 200

    assert "admin/seo/confirm_change.html" in [
        template.name for template in response.templates
    ]

    # قبل از تأیید نباید چیزی ذخیره شده باشد
    settings.refresh_from_db()

    assert settings.allow_crawling is False
    assert SEOSettingsLog.objects.count() == 0

    # ساخت توکن معتبر برای شبیه‌سازی تأیید مدیر
    confirmation_token = signing.dumps(
        {
            "user_id": user.pk,
            "object_id": str(settings.pk),
            "old_value": False,
            "new_value": True,
            "version": settings.version,
        },
        salt="seo-crawl-confirmation",
    )

    # مرحله دوم: تأیید و ذخیره
    response = client.post(
        url,
        {
            "allow_crawling": "on",
            "_save": "Save",
            "_seo_confirmation": confirmation_token,
        },
    )

    assert response.status_code == 302

    # بررسی ذخیره در دیتابیس
    settings.refresh_from_db()

    assert settings.allow_crawling is True

    # بررسی تاریخچه تغییرات
    assert SEOSettingsLog.objects.count() == 1

    log = SEOSettingsLog.objects.first()

    assert log.changed_by == user
    assert log.old_value is False
    assert log.new_value is True


@pytest.mark.django_db
def test_seo_change_cannot_bypass_confirmation(client):
    user = get_user_model().objects.create_superuser(
        username="security_admin",
        email="security@example.com",
        password="TestPassword123!",
    )

    settings = SEOSettings.get_settings()
    client.force_login(user)

    url = reverse(
        "admin:seo_seosettings_change",
        args=[settings.pk],
    )

    # تلاش برای دور زدن تأیید با توکن جعلی
    response = client.post(
        url,
        {
            "allow_crawling": "on",
            "_save": "Save",
            "_seo_confirmation": "fake-token",
        },
    )

    # باید دوباره صفحه تأیید نمایش داده شود
    assert response.status_code == 200

    assert "admin/seo/confirm_change.html" in [
        template.name for template in response.templates
    ]

    # نباید هیچ تغییری در دیتابیس ثبت شده باشد
    settings.refresh_from_db()

    assert settings.allow_crawling is False
    assert SEOSettingsLog.objects.count() == 0


@pytest.mark.django_db
def test_seo_admin_rejects_stale_confirmation(client):
    user = get_user_model().objects.create_superuser(
        username="stale_admin",
        email="stale@example.com",
        password="TestPassword123!",
    )

    settings = SEOSettings.get_settings()
    client.force_login(user)

    url = reverse(
        "admin:seo_seosettings_change",
        args=[settings.pk],
    )

    old_version = settings.version

    # Generate confirmation token for the current version.
    token = signing.dumps(
        {
            "user_id": user.pk,
            "object_id": str(settings.pk),
            "old_value": False,
            "new_value": True,
            "version": old_version,
        },
        salt="seo-crawl-confirmation",
    )

    # Another update changes the version.
    SEOSettings.objects.filter(pk=settings.pk).update(
        version=old_version + 1,
    )

    # Attempt to confirm using the old token.
    response = client.post(
        url,
        {
            "allow_crawling": "on",
            "_save": "Save",
            "_seo_confirmation": token,
        },
    )

    assert response.status_code in (200, 409)

    settings.refresh_from_db()

    assert settings.allow_crawling is False
    assert settings.version == old_version + 1
    assert SEOSettingsLog.objects.count() == 0
