from django.test import TestCase
from rest_framework.exceptions import ValidationError

from cms.models import Page
from cms.services.page_service import RevisionConflict, save_page, set_publication
from cms.tests.helpers import block, content, user


class PageServiceTests(TestCase):
    def setUp(self):
        self.actor = user(is_staff=True)

    def test_create_draft_with_readable_slug(self):
        page = save_page(self.actor, content(title="رم ۱۶ گیگ"))
        self.assertEqual(page.slug, "رم-16-گیگ")
        self.assertFalse(page.is_published)
        self.assertEqual(page.published, {})

    def test_automatic_slug_collision_gets_suffix(self):
        first = save_page(self.actor, content())
        second = save_page(self.actor, content())
        self.assertNotEqual(first.slug, second.slug)

    def test_manual_duplicate_slug_is_rejected(self):
        save_page(self.actor, content(slug="about"))
        with self.assertRaises(ValidationError):
            save_page(self.actor, content(slug="about"))
        self.assertEqual(Page.objects.count(), 1)

    def test_saved_changes_do_not_replace_published_snapshot(self):
        page = save_page(self.actor, content())
        page = set_publication(self.actor, page.pk, page.revision, True)
        page = save_page(self.actor, content(title="عنوان جدید", revision=page.revision), page.pk)
        self.assertEqual(page.title, "عنوان جدید")
        self.assertEqual(page.published["title"], "درباره ما")
        page = set_publication(self.actor, page.pk, page.revision, True)
        self.assertEqual(page.published["title"], "عنوان جدید")

    def test_stale_save_is_rejected_without_overwrite(self):
        page = save_page(self.actor, content())
        old = page.revision
        save_page(self.actor, content(title="نسخه تازه", revision=old), page.pk)
        with self.assertRaises(RevisionConflict):
            save_page(self.actor, content(title="نسخه قدیمی", revision=old), page.pk)
        page.refresh_from_db()
        self.assertEqual(page.title, "نسخه تازه")

    def test_stale_publish_is_rejected(self):
        page = save_page(self.actor, content())
        save_page(self.actor, content(revision=page.revision), page.pk)
        with self.assertRaises(RevisionConflict):
            set_publication(self.actor, page.pk, page.revision, True)

    def test_hide_keeps_content_and_allows_republication(self):
        page = save_page(self.actor, content())
        page = set_publication(self.actor, page.pk, page.revision, True)
        page = set_publication(self.actor, page.pk, page.revision, False)
        self.assertFalse(page.is_published)
        self.assertTrue(page.published)
        page = set_publication(self.actor, page.pk, page.revision, True)
        self.assertTrue(page.is_published)

    def test_slug_locked_after_first_publication(self):
        page = save_page(self.actor, content())
        page = set_publication(self.actor, page.pk, page.revision, True)
        with self.assertRaises(ValidationError):
            save_page(self.actor, content(slug="new", revision=page.revision), page.pk)

    def test_empty_page_cannot_publish(self):
        page = save_page(self.actor, content(blocks=[]))
        with self.assertRaises(ValidationError):
            set_publication(self.actor, page.pk, page.revision, True)

    def test_blocks_keep_order_and_switch(self):
        a, b = block(), {**block(), "id": "block-2", "enabled": False}
        page = save_page(self.actor, content(blocks=[b, a]))
        self.assertEqual(page.blocks[0]["id"], "block-2")
        self.assertFalse(page.blocks[0]["enabled"])

    def test_unknown_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            save_page(self.actor, content(is_published=True))

    def test_invalid_link_and_arbitrary_block_are_rejected(self):
        for href in ["javascript:alert(1)", "//evil.example", "data:text/html,x", "/\\evil", "https://user:pass@example.com"]:
            with self.subTest(href=href), self.assertRaises(ValidationError):
                save_page(self.actor, content(blocks=[block("buttons", items=[{"label": "کلیک", "href": href}])]))
        with self.assertRaises(ValidationError):
            save_page(self.actor, content(blocks=[block("html", html="<script>x</script>")]))

    def test_duplicate_block_ids_rejected(self):
        with self.assertRaises(ValidationError):
            save_page(self.actor, content(blocks=[block(), block()]))

    def test_missing_image_rejected(self):
        with self.assertRaises(ValidationError):
            save_page(self.actor, content(blocks=[block("image", image_id=None, alt="تصویر", caption="")]))
