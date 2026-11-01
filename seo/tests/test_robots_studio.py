import copy
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from cms.tests.helpers import user
from seo.models import RobotsDocument
from seo.robots_api import RobotsStudioView
from seo.services.robots_engine import PolicyError, evaluate, render_document, validate_document
from seo.services.robots_service import RobotsConflict, current_document, update_document


def document(action="allow"):
    return {"version": 1, "groups": [{"id": "all", "agent": "*", "enabled": True, "rules": [{"id": "root", "action": action, "scope": "pattern", "path": "/", "enabled": True}]}], "sitemaps": []}


@override_settings(SITE_PUBLIC_URL="https://shop.example")
class RobotsStudioTests(TestCase):
    def setUp(self):
        self.actor = user(is_staff=True, is_superuser=True)

    def test_draft_never_changes_public_file(self):
        row = current_document()
        before = self.client.get("/robots.txt").content
        saved = update_document(actor=self.actor, expected_revision=row.revision, document=document(), action="save")
        self.assertEqual(saved.draft, document())
        self.assertEqual(self.client.get("/robots.txt").content, before)

    def test_publish_changes_public_output_atomically(self):
        row = current_document()
        saved = update_document(actor=self.actor, expected_revision=row.revision, document=document(), action="publish")
        self.assertEqual(saved.draft, saved.published)
        self.assertEqual(self.client.get("/robots.txt").content.decode(), render_document(document()))
        self.assertEqual(saved.published_revision, saved.revision)

    def test_invalid_publish_does_not_change_draft_or_live(self):
        row = current_document()
        broken = document()
        broken["groups"][0]["agent"] = "*\nDisallow: /"
        with self.assertRaises(PolicyError):
            update_document(actor=self.actor, expected_revision=row.revision, document=broken, action="publish")
        row.refresh_from_db()
        self.assertEqual(row.revision, 1)

    def test_stale_revision_cannot_overwrite(self):
        row = current_document()
        update_document(actor=self.actor, expected_revision=row.revision, document=document(), action="save")
        with self.assertRaises(RobotsConflict):
            update_document(actor=self.actor, expected_revision=row.revision, document=document("disallow"), action="publish")

    def test_reset_discards_only_draft(self):
        row = current_document()
        live = copy.deepcopy(row.published)
        saved = update_document(actor=self.actor, expected_revision=row.revision, document=document(), action="save")
        reset = update_document(actor=self.actor, expected_revision=saved.revision, action="reset")
        self.assertEqual(reset.draft, live)
        self.assertEqual(reset.published, live)

    def test_service_rejects_actor_without_permission(self):
        actor = Mock(is_active=True)
        actor.has_perm.return_value = False
        with self.assertRaises(PermissionDenied):
            update_document(actor=actor, expected_revision=1, document=document(), action="publish")

    def test_viewer_can_test_but_cannot_publish(self):
        viewer = Mock()
        viewer.has_perm.side_effect = lambda permission: permission == "seo.view_seosettings"
        request = SimpleNamespace(user=viewer, data={"action": "test", "source": "draft", "document": document(), "path": "/products", "agent": "Googlebot"})
        result = RobotsStudioView().post(request)
        self.assertTrue(result.data["allowed"])
        request.data = {"action": "publish", "expected_revision": 1, "document": document()}
        with self.assertRaises(PermissionDenied):
            RobotsStudioView().post(request)

    def test_published_source_ignores_unsaved_test_document(self):
        row = current_document()
        update_document(actor=self.actor, expected_revision=row.revision, document=document("disallow"), action="publish")
        viewer = Mock()
        viewer.has_perm.return_value = True
        request = SimpleNamespace(user=viewer, data={"action": "test", "source": "published", "document": document("allow"), "path": "/products"})
        self.assertFalse(RobotsStudioView().post(request).data["allowed"])

    def test_legacy_rule_is_not_public_after_studio_publish(self):
        from seo.models import SEOSettings
        row = current_document()
        update_document(actor=self.actor, expected_revision=row.revision, document=document("disallow"), action="publish")
        settings = SEOSettings.get_settings()
        settings.allow_crawling = True
        settings.save()
        self.assertIn("Disallow: /", self.client.get("/robots.txt").content.decode())

    def test_utf8_plaintext_head(self):
        response = self.client.head("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
