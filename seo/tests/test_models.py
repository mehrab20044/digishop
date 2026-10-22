import pytest

from seo.models import SEOSettings


@pytest.mark.django_db
def test_seo_settings_is_singleton():
    first = SEOSettings.get_settings()
    second = SEOSettings.get_settings()

    assert first.pk == second.pk == 1
    assert SEOSettings.objects.count() == 1
