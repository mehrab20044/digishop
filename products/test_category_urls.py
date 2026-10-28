from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from products.models import Category
from products.services.category_service import save_category
from products.services.category_url_service import (
    current_paths,
    normalize_slug,
    resolve_path,
)


class CategoryURLTests(TestCase):
    def create(self, name, **kwargs):
        return save_category(data={"name": name, **kwargs})

    def test_persian_normalization(self):
        self.assertEqual(normalize_slug("رم ۱۶\u200cگیگ"), "رم-16-گیگ")
        self.assertEqual(normalize_slug("DDR5"), "ddr5")

    def test_auto_slug_and_rename_stability(self):
        category = self.create("رم")
        self.assertEqual(category.slug, "رم")
        category = save_category(category_id=category.pk, data={"name": "حافظه رم"})
        self.assertEqual(category.slug, "رم")

    def test_duplicate_names_different_parents(self):
        a = self.create("لپتاپ")
        b = self.create("کامپیوتر")
        x = self.create("گیمینگ", parent_id=a.pk)
        y = self.create("گیمینگ", parent_id=b.pk)
        self.assertNotEqual(x.slug, y.slug)

    def test_parent_slug_change_preserves_descendant_alias(self):
        parent = self.create("رم")
        child = self.create("DDR5", parent_id=parent.pk)
        old = current_paths()[child.pk]
        save_category(category_id=parent.pk, data={"slug": "memory"})
        resolved, path = resolve_path(old)
        self.assertEqual(resolved.pk, child.pk)
        self.assertEqual(path, "memory/ddr5")

    def test_move_preserves_old_url(self):
        a = self.create("رم")
        b = self.create("قطعات")
        child = self.create("DDR5", parent_id=a.pk)
        old = current_paths()[child.pk]
        save_category(category_id=child.pk, data={"parent_id": b.pk})
        self.assertEqual(resolve_path(old)[1], "قطعات/ddr5")

    def test_invalid_branch_rejected(self):
        self.create("رم")
        self.assertIsNone(resolve_path("رم/ناموجود"))
        response = self.client.get(reverse("category-resolve"), {"path": "رم/ناموجود"})
        self.assertEqual(response.status_code, 404)

    def test_alias_not_reassigned(self):
        category = self.create("رم")
        save_category(category_id=category.pk, data={"slug": "memory"})
        with self.assertRaises(ValidationError):
            Category.objects.create(name="دسته دیگر", slug="رم")

    def test_old_page_redirect(self):
        category = self.create("رم")
        save_category(category_id=category.pk, data={"slug": "memory"})
        response = self.client.get("/products/category/رم?ordering=created_at")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/products/category/memory?ordering=created_at")
