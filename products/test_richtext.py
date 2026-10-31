import tempfile
from pathlib import Path

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from products.models import Category, Product
from products.services.richtext_service import sanitize_richtext


class RichTextTests(TestCase):
    def setUp(self):
        # Category writes are tested separately; this fixture does not change a tree.
        self.category = Category.objects.bulk_create([Category(name="آزمایشی", slug="rich-test", description="توضیح اختصاصی دسته\nخط دوم")])[0]
        self.product = Product.objects.create(category=self.category, name="کالای نمونه", slug="rich-product", price=100, stock=2, long_description="متن قدیمی <نمونه>")

    def test_old_plain_text_remains_untouched(self):
        self.product.name = "نام جدید"
        self.product.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.long_description, "متن قدیمی <نمونه>")
        self.assertEqual(self.product.long_description_html, "")

    def test_formatting_saved_and_plain_copy_generated(self):
        self.product.long_description_html = '<h2>عنوان</h2><p><strong>بولد</strong> و <span style="font-family:tahoma;font-size:24px">متن</span></p>'
        self.product.full_clean(exclude=["image"])
        self.product.save()
        self.product.refresh_from_db()
        self.assertIn("<strong>", self.product.long_description_html)
        self.assertIn("font-size:24px", self.product.long_description_html)
        self.assertIn("بولد", self.product.long_description)
        self.assertNotIn("<strong>", self.product.long_description)

    def test_script_events_and_layout_css_removed(self):
        payload = '<script>alert(1)</script><svg onload="alert(1)"></svg><p onclick="alert(1)"><span style="position:fixed;font-size:999px;color:#ff0000;font-family:evil">خوب</span><a href="javascript:alert(1)">لینک</a></p>'
        clean = sanitize_richtext(payload)
        for bad in ["script", "alert", "onclick", "position", "999px", "evil", "javascript", "<svg"]:
            self.assertNotIn(bad, clean)
        self.assertIn("خوب", clean)
        self.assertIn("#ff0000", clean)

    def test_malformed_html_is_safe_and_cleaning_idempotent(self):
        samples = ['<math><mtext><table><mglyph><style><!--</style><img src=x onerror=alert(1)>', '<p><a href="//evil.example">x</a><iframe srcdoc="x">x</iframe>', '<p style="text-align:center">متن &amp; تست</p>']
        for html in samples:
            clean = sanitize_richtext(html)
            self.assertEqual(sanitize_richtext(clean), clean)
            self.assertNotIn("onerror", clean)
            self.assertNotIn("iframe", clean)
            self.assertNotIn("//evil", clean)

    def test_legacy_plain_edit_clears_old_formatting(self):
        self.product.long_description_html = '<p><strong>قدیمی</strong></p>'
        self.product.save()
        self.product.long_description = "ویرایش از مسیر قدیمی"
        self.product.full_clean(exclude=["image"])
        self.product.save()
        self.product.refresh_from_db()
        self.assertEqual(self.product.long_description, "ویرایش از مسیر قدیمی")
        self.assertEqual(self.product.long_description_html, "")

    def test_stock_only_save_does_not_change_descriptions(self):
        self.product.long_description_html = '<p><strong>متن</strong></p>'
        self.product.save()
        self.product.stock = 9
        self.product.save(update_fields=["stock"])
        self.product.refresh_from_db()
        self.assertIn("<strong>", self.product.long_description_html)

    def test_public_api_only_exposes_sanitized_html(self):
        Product.objects.filter(pk=self.product.pk).update(long_description_html='<p onclick="bad()"><strong>متن</strong></p>')
        response = self.client.get(f"/products/api/v1/products/{self.product.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("onclick", response.json()["long_description_html"])

    def test_oversized_content_rejected(self):
        with self.assertRaises(ValidationError):
            sanitize_richtext("x" * 160001)

    def test_category_description_in_server_html(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory)/"frontend/dist/index.html"
            index.parent.mkdir(parents=True)
            index.write_text('<html><head><title>Shop</title></head><body><div id="root"></div></body></html>')
            with override_settings(BASE_DIR=directory):
                from django.test import RequestFactory

                from products.category_url_views import category_page
                response = category_page(RequestFactory().get("/products/category/rich-test"), "rich-test")
                self.assertEqual(response.status_code, 200)
                self.assertIn("توضیح اختصاصی دسته", response.content.decode())
