import copy
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from cms.api.v1.banner_views import BannerView
from cms.services.banner_service import get_banners, public_banners, update_banners
from cms.services.page_service import RevisionConflict
from cms.services.theme_service import get_theme
from cms.tests.helpers import user


def banner(**values):
    return {"id": "test-banner", "placement": "hero", "title": "پیشنهاد تازه", "body": "توضیح", "image_id": None, "mobile_image_id": None, "alt": "", "href": "/products", "button_label": "دیدن", "enabled": True, "show_text": True, "start_at": None, "end_at": None, **values}


class BannerTests(TestCase):
    def setUp(self):
        self.actor = user(is_staff=True, is_superuser=True)

    def publish(self, rows):
        row = update_banners(self.actor, get_banners().revision, rows)
        return update_banners(self.actor, row.revision, publish=True)

    def test_legacy_banner_preserved(self):
        theme = get_theme()
        self.assertEqual(get_banners().published[0]["title"], theme.published["banner"]["title"])

    def test_draft_does_not_leak(self):
        old = copy.deepcopy(get_banners().published)
        update_banners(self.actor, get_banners().revision, [banner(title="PRIVATE DRAFT")])
        self.assertEqual(get_banners().published, old)
        response = self.client.get("/api/v1/content/banners/")
        self.assertNotContains(response, "PRIVATE DRAFT")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_order_and_placement_are_backend_defined(self):
        self.publish([banner(id="two", title="دوم"), banner(id="tile", placement="tiles"), banner(id="one", title="اول")])
        result = public_banners()
        self.assertEqual([row["id"] for row in result["hero"]], ["two", "one"])
        self.assertEqual([row["id"] for row in result["tiles"]], ["tile"])

    def test_disabled_and_future_banners_not_public(self):
        now = timezone.now()
        future = now + timedelta(hours=1)
        self.publish([banner(id="off", enabled=False), banner(id="future", start_at=future.isoformat()), banner(id="expired", end_at=(now-timedelta(seconds=1)).isoformat()), banner(id="live")])
        result = public_banners(now)
        self.assertEqual([row["id"] for row in result["hero"]], ["live"])
        self.assertEqual(result["next_change_at"], future.isoformat())

    def test_end_boundary_is_exclusive_and_start_inclusive(self):
        now = timezone.now()
        self.publish([banner(id="start", start_at=now.isoformat()), banner(id="end", end_at=now.isoformat())])
        self.assertEqual([row["id"] for row in public_banners(now)["hero"]], ["start"])

    def test_invalid_dates_and_links_rejected(self):
        cases = [banner(href="javascript:alert(1)"), banner(start_at="2026-01-01T12:00:00"), banner(start_at="2026-01-02T12:00:00Z", end_at="2026-01-01T12:00:00Z")]
        for row in cases:
            with self.subTest(row=row), self.assertRaises(ValidationError):
                update_banners(self.actor, get_banners().revision, [row])

    def test_stale_update_rejected(self):
        old = get_banners().revision
        update_banners(self.actor, old, [])
        with self.assertRaises(RevisionConflict):
            update_banners(self.actor, old, publish=True)

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValidationError):
            update_banners(self.actor, get_banners().revision, [banner(), banner()])

    def test_owner_api_requires_management_purpose(self):
        factory = APIRequestFactory()
        request = factory.get("/")
        force_authenticate(request, user=self.actor, token={"purpose": "customer"})
        self.assertEqual(BannerView.as_view()(request).status_code, 403)
        request = factory.get("/")
        force_authenticate(request, user=self.actor, token={"purpose": "management"})
        self.assertEqual(BannerView.as_view()(request).status_code, 200)

    def test_staff_without_banner_permission_denied(self):
        member = user("09120000002", is_staff=True)
        request = APIRequestFactory().get("/")
        force_authenticate(request, user=member, token={"purpose": "management"})
        self.assertEqual(BannerView.as_view()(request).status_code, 403)
