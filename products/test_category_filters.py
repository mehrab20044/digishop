from django.test import TestCase
from rest_framework.test import APIClient

from products.models import Category, Product


class CategoryFilterTests(TestCase):
    url = "/products/api/v1/products/"

    def setUp(self):
        self.client = APIClient()

        self.digital = self.category("دیجیتال", "digital")
        self.mobile = self.category(
            "موبایل",
            "mobile",
            parent=self.digital,
        )
        self.smartphone = self.category(
            "گوشی هوشمند",
            "smartphone",
            parent=self.mobile,
        )
        self.android = self.category(
            "اندروید",
            "android",
            parent=self.smartphone,
        )
        self.budget = self.category(
            "اقتصادی",
            "budget",
            parent=self.android,
        )

        self.samsung = self.category("سامسونگ", "samsung")
        self.galaxy = self.category(
            "سری گلکسی",
            "galaxy",
            parent=self.samsung,
        )
        self.television = self.category("تلویزیون", "television")

        self.samsung_phone = self.product(
            "گوشی سامسونگ",
            "samsung-phone",
            self.budget,
            memberships=[self.budget, self.galaxy],
        )
        self.other_phone = self.product(
            "گوشی دیگر",
            "other-phone",
            self.mobile,
            memberships=[self.mobile],
        )
        self.samsung_tv = self.product(
            "تلویزیون سامسونگ",
            "samsung-tv",
            self.television,
            memberships=[self.television, self.samsung],
        )
        self.unavailable_phone = self.product(
            "گوشی ناموجود",
            "unavailable-phone",
            self.mobile,
            memberships=[self.mobile],
            stock=0,
        )
        self.draft_phone = self.product(
            "پیش‌نویس",
            "draft-phone",
            self.mobile,
            memberships=[self.mobile, self.samsung],
            status=Product.Status.DRAFT,
        )

    def category(self, name, slug, parent=None):
        return Category.objects.create(
            name=name,
            slug=slug,
            parent=parent,
        )

    def product(
        self,
        name,
        slug,
        primary,
        *,
        memberships,
        stock=5,
        status=Product.Status.PUBLISHED,
    ):
        product = Product.objects.create(
            name=name,
            slug=slug,
            category=primary,
            price=100000,
            stock=stock,
            status=status,
            is_active=True,
        )
        product.categories.set(memberships)
        return product

    def result_ids(self, params):
        response = self.client.get(self.url, params)

        self.assertEqual(response.status_code, 200, response.data)

        data = response.data
        rows = data["results"] if isinstance(data, dict) else data

        return {row["id"] for row in rows}

    def test_parent_includes_products_from_fifth_level(self):
        ids = self.result_ids({"category": self.digital.pk})

        self.assertIn(self.samsung_phone.pk, ids)
        self.assertNotIn(self.samsung_tv.pk, ids)
        self.assertNotIn(self.draft_phone.pk, ids)

    def test_direct_samsung_includes_products_across_types(self):
        ids = self.result_ids({"category": self.samsung.pk})

        self.assertEqual(
            ids,
            {self.samsung_phone.pk, self.samsung_tv.pk},
        )

    def test_selected_branches_return_intersection(self):
        ids = self.result_ids({
            "categories": f"{self.mobile.pk},{self.samsung.pk}",
        })

        self.assertEqual(ids, {self.samsung_phone.pk})

    def test_category_and_categories_also_intersect(self):
        ids = self.result_ids({
            "category": self.mobile.pk,
            "categories": str(self.samsung.pk),
        })

        self.assertEqual(ids, {self.samsung_phone.pk})

    def test_multiple_memberships_do_not_duplicate_product(self):
        self.samsung_phone.categories.add(
            self.mobile,
            self.samsung,
        )

        response = self.client.get(
            self.url,
            {
                "categories": (
                    f"{self.digital.pk},{self.samsung.pk}"
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.samsung_phone.pk,
        )

    def test_primary_category_still_matches_without_membership(self):
        self.other_phone.categories.clear()

        ids = self.result_ids({"category": self.mobile.pk})

        self.assertIn(self.other_phone.pk, ids)

    def test_related_categories_do_not_automatically_expand_results(self):
        self.mobile.related_categories.add(self.samsung)

        ids = self.result_ids({"category": self.mobile.pk})

        self.assertIn(self.samsung_phone.pk, ids)
        self.assertNotIn(self.samsung_tv.pk, ids)

    def test_unavailable_product_remains_in_default_results(self):
        ids = self.result_ids({"category": self.mobile.pk})

        self.assertIn(self.unavailable_phone.pk, ids)

    def test_in_stock_filter_excludes_unavailable_product(self):
        ids = self.result_ids({
            "category": self.mobile.pk,
            "in_stock": "true",
        })

        self.assertNotIn(self.unavailable_phone.pk, ids)
        self.assertIn(self.other_phone.pk, ids)

    def test_invalid_category_lists_are_rejected(self):
        values = (
            "abc",
            "0",
            "-1",
            f"{self.mobile.pk},",
            f"{self.mobile.pk},999999999",
            "999999999999999999999999",
        )

        for value in values:
            with self.subTest(value=value):
                response = self.client.get(
                    self.url,
                    {"categories": value},
                )
                self.assertEqual(response.status_code, 400)

    def test_unknown_single_category_is_rejected(self):
        response = self.client.get(
            self.url,
            {"category": 999999999},
        )

        self.assertEqual(response.status_code, 400)

    def test_repeated_category_id_does_not_change_results(self):
        ids = self.result_ids({
            "categories": f"{self.samsung.pk},{self.samsung.pk}",
        })

        self.assertEqual(
            ids,
            {self.samsung_phone.pk, self.samsung_tv.pk},
        )
