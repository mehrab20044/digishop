from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from products.models import Category, Product


class SimpleCategoryUXTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.laptops = Category.objects.create(name="لپ‌تاپ", slug="ux-laptops")
        self.asus = Category.objects.create(name="ایسوس", slug="ux-asus", parent=self.laptops)
        self.lenovo = Category.objects.create(name="لنوو", slug="ux-lenovo", parent=self.laptops)
        self.asus_gaming = Category.objects.create(name="گیمینگ", slug="ux-asus-gaming", parent=self.asus)

    def test_same_name_under_different_parents_is_allowed(self):
        category = Category(name="گیمینگ", slug="ux-lenovo-gaming", parent=self.lenovo)
        category.full_clean()
        category.save()
        self.assertNotEqual(category.pk, self.asus_gaming.pk)

    def test_duplicate_sibling_name_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="گیمینگ", slug="ux-other-gaming", parent=self.asus)

    def test_duplicate_root_name_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Category.objects.create(name="لپ‌تاپ", slug="ux-other-laptops")

    def test_persian_slug_is_accepted(self):
        category = Category(name="دستهٔ جدید", slug="نامک-فارسی")
        category.full_clean()
        self.assertEqual(category.slug, "نامک-فارسی")

    def test_tree_keeps_brand_and_usage_in_their_branch(self):
        response = self.client.get("/products/api/v1/categories/tree/")
        self.assertEqual(response.status_code, 200)
        root = next(row for row in response.data if row["id"] == self.laptops.pk)
        asus = next(row for row in root["children"] if row["id"] == self.asus.pk)
        self.assertEqual([row["id"] for row in asus["children"]], [self.asus_gaming.pk])

    def test_leaf_product_is_visible_in_all_ancestor_pages(self):
        product = Product.objects.create(
            category=self.asus_gaming,
            name="لپ‌تاپ آزمایشی",
            slug="ux-gaming-product",
            price=100000,
            stock=2,
            status=Product.Status.PUBLISHED,
            is_active=True,
        )
        product.categories.add(self.asus_gaming)
        for category in (self.laptops, self.asus, self.asus_gaming):
            with self.subTest(category=category.pk):
                response = self.client.get("/products/api/v1/products/", {"category": category.pk})
                self.assertEqual(response.status_code, 200)
                self.assertIn(product.pk, [row["id"] for row in response.data["results"]])
        response = self.client.get("/products/api/v1/products/", {"category": self.lenovo.pk})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(product.pk, [row["id"] for row in response.data["results"]])
