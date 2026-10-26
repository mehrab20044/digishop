import pytest
from django.contrib.auth import get_user_model

from seo.models import SEOSettings, SEOSettingsLog
from seo.services.seo_services import SEOService, SEOSettingsConflict


@pytest.mark.django_db
def test_seo_service_rejects_stale_version():
    user = get_user_model().objects.create_superuser(
        phone="09100000001",
        email="version@example.com",
        password="TestPassword123!",
    )

    settings = SEOSettings.get_settings()
    original_version = settings.version

    # First update succeeds.
    updated = SEOService.update_crawling(
        expected_version=original_version,
        allow_crawling=True,
        user=user,
    )

    assert updated.allow_crawling is True
    assert updated.version == original_version + 1

    # Second update uses an outdated version.
    with pytest.raises(SEOSettingsConflict):
        SEOService.update_crawling(
            expected_version=original_version,
            allow_crawling=False,
            user=user,
        )

    # The rejected update must not change data or history.
    settings.refresh_from_db()

    assert settings.allow_crawling is True
    assert settings.version == original_version + 1
    assert SEOSettingsLog.objects.count() == 1
