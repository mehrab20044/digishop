import re
from unittest.mock import Mock

from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from cms.models import Page
from cms.tests.helpers import user
from products.models import Category, Product
from products.services.category_service import save_category
from seo.models import PageSearchRule, SEOSettings
from seo.page_rules_api import PageRulesView
from seo.services.canonical_service import canonical_document
from seo.services.page_rules import RuleConflict, build_robots, save_rule, sitemap_ids


@override_settings(SITE_PUBLIC_URL="https://shop.example")
class PageRuleTests(TestCase):
    def setUp(self):
        self.actor = user(is_staff=True, is_superuser=True)
        self.settings = SEOSettings.get_settings()
        self.category = Category.objects.create(name="رم", slug="ram")
        self.product = Product.objects.create(name="کالای تست", slug="robots-product", category=self.category, price=1000, stock=1, is_active=True, status=Product.Status.PUBLISHED)
        self.page = Page.objects.create(title="Draft", slug="about", is_published=True, published={"title": "Public"})

    def write(self, kind="product", object_id=None, version=0, crawl="block", indexing="inherit"):
        return save_rule(actor=self.actor, kind=kind, object_id=self.product.pk if object_id is None else object_id, expected_version=version, crawl=crawl, indexing=indexing)

    def test_default_preserved(self):
        self.assertEqual(build_robots(), "User-agent: *\nDisallow: /\n")

    def test_specific_allow_overrides_blocked_default(self):
        self.write(crawl="allow")
        robots = build_robots()
        self.assertIn("Disallow: /\n", robots)
        self.assertIn(f"Allow: /products/{self.product.pk}$\n", robots)
        self.assertIn(f"Allow: /products/{self.product.pk}?\n", robots)

    def test_specific_block_does_not_block_other_product_or_children(self):
        self.settings.allow_crawling = True
        self.settings.save()
        self.write()
        robots = build_robots()
        path = f"/products/{self.product.pk}"
        patterns = [line.split(": ", 1)[1] for line in robots.splitlines() if line.startswith("Disallow: ")]
        def matches(url):
            return any(re.match(re.escape(pattern[:-1]) + r"$" if pattern.endswith("$") else re.escape(pattern), url) for pattern in patterns)
        self.assertTrue(matches(path))
        self.assertTrue(matches(path + "?utm_source=x"))
        self.assertFalse(matches(path + "3"))
        self.assertFalse(matches(path + "/child"))

    def test_category_rename_updates_current_and_alias_rules(self):
        self.write(kind="category", object_id=self.category.pk)
        save_category(category_id=self.category.pk, data={"slug": "memory"})
        robots = build_robots()
        self.assertIn("Disallow: /products/category/ram$", robots)
        self.assertIn("Disallow: /products/category/memory$", robots)

    def test_optimistic_version_and_log(self):
        first = self.write()
        self.assertEqual(first["version"], 1)
        with self.assertRaises(RuleConflict):
            self.write(crawl="allow")
        self.assertEqual(PageSearchRule.objects.get(kind="product", object_id=self.product.pk).crawl, "block")
        from django.contrib.admin.models import LogEntry
        self.assertTrue(LogEntry.objects.filter(user_id=self.actor.pk, object_id=str(PageSearchRule.objects.get().pk)).exists())

    def test_inherit_removes_only_its_robots_override(self):
        first = self.write()
        self.write(version=first["version"], crawl="inherit")
        self.assertNotIn(f"/products/{self.product.pk}", build_robots())

    def test_noindex_is_separate_from_crawl(self):
        from django.test import RequestFactory
        self.write(crawl="allow", indexing="noindex")
        self.assertIn(f"Allow: /products/{self.product.pk}$", build_robots())
        request = RequestFactory().get(f"/products/{self.product.pk}")
        data = canonical_document(request, request.get_full_path())
        self.assertEqual(data["robots"], "noindex, follow")
        self.assertEqual(data["canonical"], f"https://shop.example/products/{self.product.pk}")
        self.assertNotIn(self.product.pk, sitemap_ids("product", [self.product.pk]))

    def test_legacy_crawl_does_not_change_published_sitemap(self):
        self.assertEqual(sitemap_ids("product", [self.product.pk]), set())
        self.write(crawl="allow")
        self.assertEqual(sitemap_ids("product", [self.product.pk]), set())

    def test_unpublished_page_does_not_emit_rule(self):
        self.write(kind="page", object_id=self.page.pk)
        self.page.is_published = False
        self.page.save()
        self.assertNotIn("/pages/about", build_robots())

    def test_post_permission_checked_before_mutation(self):
        actor = Mock()
        actor.has_perm.return_value = False
        request = Mock(user=actor)
        with self.assertRaises(PermissionDenied):
            PageRulesView().post(request)
        self.assertFalse(PageSearchRule.objects.exists())
