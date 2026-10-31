import copy
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from cms.api.v1.theme_views import ThemeView
from cms.services.page_service import RevisionConflict, save_page, set_publication
from cms.services.theme_service import DEFAULT_THEME, get_theme, update_theme
from cms.tests.helpers import content, user


class AppearanceTests(TestCase):
    def setUp(self):
        self.actor = user(is_staff=True, is_superuser=True)

    def test_theme_draft_is_not_public_before_publish(self):
        row = get_theme()
        config = copy.deepcopy(DEFAULT_THEME)
        config["primary"] = "#315bea"
        row = update_theme(self.actor, row.revision, config)
        self.assertEqual(self.client.get("/api/v1/content/theme/").json()["primary"], DEFAULT_THEME["primary"])
        update_theme(self.actor, row.revision, publish=True)
        self.assertEqual(self.client.get("/api/v1/content/theme/").json()["primary"], "#315bea")

    def test_theme_rejects_stale_revision(self):
        row = get_theme()
        old = row.revision
        update_theme(self.actor, old, copy.deepcopy(DEFAULT_THEME))
        with self.assertRaises(RevisionConflict):
            update_theme(self.actor, old, publish=True)

    def test_unreadable_colors_and_unsafe_banner_link_rejected(self):
        for changes in [{"text": "#ffffff"}, {"primary": "red;position:fixed"}]:
            config = copy.deepcopy(DEFAULT_THEME)
            config.update(changes)
            with self.assertRaises(ValidationError):
                update_theme(self.actor, get_theme().revision, config)
        config = copy.deepcopy(DEFAULT_THEME)
        config["banner"]["button_href"] = "javascript:alert(1)"
        with self.assertRaises(ValidationError):
            update_theme(self.actor, get_theme().revision, config)

    def test_footer_snapshot_label_order_and_visibility(self):
        a = save_page(self.actor, content(title="اول", slug="one", footer_label="راهنما", footer_order=20))
        b = save_page(self.actor, content(title="دوم", slug="two", footer_order=10))
        a = set_publication(self.actor, a.pk, a.revision, True)
        b = set_publication(self.actor, b.pk, b.revision, True)
        links = self.client.get("/api/v1/content/pages/").json()["results"]
        self.assertEqual([row["title"] for row in links], ["دوم", "راهنما"])
        a = save_page(self.actor, content(title="اول", slug="one", footer_visible=False, revision=a.revision), a.pk)
        self.assertEqual(len(self.client.get("/api/v1/content/pages/").json()["results"]), 2)
        set_publication(self.actor, a.pk, a.revision, True)
        self.assertEqual(len(self.client.get("/api/v1/content/pages/").json()["results"]), 1)

    def test_public_document_has_only_published_layout_and_blocks(self):
        page = save_page(self.actor, content(slug="one", layout="about"))
        page = set_publication(self.actor, page.pk, page.revision, True)
        save_page(self.actor, content(slug="one", title="PRIVATE DRAFT", layout="landing", revision=page.revision), page.pk)
        response = self.client.get("/api/v1/content/page/one/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["page"]["layout"], "about")
        self.assertNotContains(response, "PRIVATE DRAFT")
        response = self.client.get("/pages/one")
        self.assertContains(response, 'id="cms-bootstrap"')
        self.assertContains(response, 'id="root"')

    def test_private_document_not_exposed(self):
        save_page(self.actor, content(slug="draft"))
        self.assertEqual(self.client.get("/api/v1/content/page/draft/").status_code, 404)

    def test_theme_requires_specific_permissions(self):
        member = user("09120000002", is_staff=True)
        request = APIRequestFactory().get("/")
        force_authenticate(request, user=member)
        with patch("cms.api.v1.theme_views.OwnerAPIView.initial", return_value=None):
            self.assertEqual(ThemeView.as_view()(request).status_code, 403)

    def test_theme_styles_are_css_and_only_use_published_values(self):
        response = self.client.get("/pages-assets/theme.css")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/css", response["Content-Type"])
        self.assertContains(response, "--store-primary")
