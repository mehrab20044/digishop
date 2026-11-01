import tempfile
from pathlib import Path

from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from seo.canonical_views import canonical_metadata, inject_canonical, storefront_document
from seo.services.canonical_service import canonical_document


@override_settings(SITE_PUBLIC_URL="https://shop.example", DEBUG=True)
class CanonicalTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_pagination_and_tracking(self):
        request = self.factory.get("/products?page=2&utm_source=test")
        data = canonical_document(request, request.get_full_path())
        self.assertEqual(data["canonical"], "https://shop.example/products?page=2")
        self.assertEqual(data["robots"], "index, follow")

    def test_search_is_not_canonicalized_to_unfiltered_catalog(self):
        request = self.factory.get("/products?search=shirt&page=2")
        data = canonical_document(request, request.get_full_path())
        self.assertIn("search=shirt", data["canonical"])
        self.assertIn("page=2", data["canonical"])
        self.assertEqual(data["robots"], "noindex, follow")

    def test_private_has_no_canonical(self):
        request = self.factory.get("/account")
        data = canonical_document(request, request.get_full_path())
        self.assertIsNone(data["canonical"])
        self.assertEqual(data["robots"], "noindex, nofollow")

    def test_origin_cannot_be_supplied_as_a_url(self):
        request = self.factory.get("/")
        with self.assertRaises(Http404):
            canonical_document(request, "https://evil.example/products")

    def test_head_is_idempotent_and_escaped(self):
        data = {"canonical": "https://shop.example/products?page=2&ordering=price", "robots": "index, follow", "title": "</script>"}
        html = '<html><head><link href="old" rel="canonical"><link rel="canonical" href="duplicate"></head></html>'
        result = inject_canonical(html, data)
        self.assertEqual(result.count('rel="canonical"'), 1)
        self.assertIn("page=2&amp;ordering=price", result)
        self.assertEqual(inject_canonical(result, data), result)
        self.assertIn("\\u003c/script>", result)

    def test_html_contains_canonical_before_javascript(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / "frontend/dist/index.html"
            index.parent.mkdir(parents=True)
            index.write_text('<html><head><title>frontend</title></head><body><div id="root"></div></body></html>')
            with self.settings(BASE_DIR=Path(directory)):
                response = storefront_document(self.factory.get("/products?page=2&utm_source=test"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'href="https://shop.example/products?page=2"')

    def test_metadata_never_caches_across_origins(self):
        response = canonical_metadata(self.factory.get("/api/v1/seo/canonical/", {"url": "/"}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_trailing_slash_redirect(self):
        response = storefront_document(self.factory.get("/products/?page=2"))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/products?page=2")
