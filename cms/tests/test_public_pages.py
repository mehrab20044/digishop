from django.test import TestCase
from django.urls import reverse

from cms.services.page_service import save_page, set_publication
from cms.tests.helpers import block, content, user


class PublicPageTests(TestCase):
    def setUp(self):
        self.actor = user(is_staff=True)
        self.page = save_page(self.actor, content(slug="about"))

    def publish(self):
        self.page = set_publication(self.actor, self.page.pk, self.page.revision, True)

    def test_draft_not_public_or_listed(self):
        self.assertEqual(self.client.get("/pages/about").status_code, 404)
        self.assertEqual(self.client.get(reverse("cms-links")).json()["results"], [])

    def test_public_is_server_rendered_and_has_canonical(self):
        self.publish()
        response = self.client.get("/pages/about")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "متن اصلی")
        self.assertContains(response, 'rel="canonical"')

    def test_public_uses_saved_snapshot_only(self):
        self.publish()
        save_page(self.actor, content(title="SECRET DRAFT", revision=self.page.revision), self.page.pk)
        response = self.client.get("/pages/about")
        self.assertNotContains(response, "SECRET DRAFT")
        self.assertNotContains(self.client.get(reverse("cms-links")), "SECRET DRAFT")

    def test_hide_removes_public_access_and_menu(self):
        self.publish()
        set_publication(self.actor, self.page.pk, self.page.revision, False)
        self.assertEqual(self.client.get("/pages/about").status_code, 404)
        self.assertEqual(self.client.get(reverse("cms-links")).json()["results"], [])

    def test_html_is_escaped_and_disabled_blocks_not_rendered(self):
        disabled = {**block(body="HIDDEN TEXT"), "id": "block-2", "enabled": False}
        self.page = save_page(self.actor, content(blocks=[block(body="<script>alert(1)</script>"), disabled], revision=self.page.revision), self.page.pk)
        self.publish()
        response = self.client.get("/pages/about")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert")
        self.assertNotContains(response, "HIDDEN TEXT")

    def test_styles_and_sitemap(self):
        self.publish()
        response = self.client.get(reverse("cms-styles"))
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertContains(self.client.get(reverse("cms-sitemap")), "/pages/about")

    def test_trailing_slash_redirects(self):
        self.publish()
        response = self.client.get("/pages/about/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/pages/about")

    def test_head_has_same_status_and_no_body(self):
        self.assertEqual(self.client.head("/pages/about").status_code, 404)
        self.publish()
        response = self.client.head("/pages/about")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
