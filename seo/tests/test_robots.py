import pytest
from django.urls import reverse

from seo.models import SEOSettings


@pytest.mark.django_db
def test_robots_disallows_crawling_by_default(client):
    response = client.get(reverse("robots_txt"))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    assert response.content.decode() == "User-agent: *\nDisallow: /\n"


@pytest.mark.django_db
def test_robots_allows_crawling_when_enabled(client):
    settings = SEOSettings.get_settings()
    settings.allow_crawling = True
    settings.save()

    response = client.get(reverse("robots_txt"))

    assert response.status_code == 200
    assert response.content.decode() == "User-agent: *\nAllow: /\n"
