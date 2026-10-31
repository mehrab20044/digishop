from contextlib import contextmanager
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from dashboard.api.v1.catalog import AttributeDefinitionsView, ProductCatalogView
from dashboard.api.v1.workspace import (
    CombinationPreviewView,
    WorkspaceBrandView,
    WorkspaceChoicesView,
    WorkspaceProductView,
    document,
)
from products.models import (
    Attribute,
    Category,
    CategoryAttribute,
    Product,
    ProductAttributeValue,
    ProductVariant,
)
from products.services.catalog_workflow import (
    preview_combinations,
    save_basic,
    save_brand,
    save_combinations,
    save_simple,
    set_publication,
)


@contextmanager
def test_lock():
    with transaction.atomic():
        yield


class CatalogWorkflowTests(TestCase):
    def setUp(self):
        for target in [
            "products.services.category_service.category_tree_write_lock",
            "products.services.attribute_service.category_tree_write_lock",
            "products.services.catalog_workflow.category_tree_write_lock",
            "dashboard.api.v1.workspace.category_tree_write_lock",
            "dashboard.api.v1.catalog.category_tree_write_lock",
        ]:
            mock = patch(target, test_lock)
            mock.start()
            self.addCleanup(mock.stop)
        self.category = Category(name="پیراهن", slug="shirts")
        Category.objects.bulk_create([self.category])
        self.item = Product.objects.create(
            name="پیراهن",
            slug="shirt",
            category=self.category,
            price=100,
            stock=4,
            status="draft",
            is_active=False,
        )
        self.axes = [
            dict(key="size", label="سایز", values=["M", "L"], required=True),
            dict(key="color", label="رنگ", values=["سفید", "مشکی"], required=True),
        ]
        User = get_user_model()
        self.admin = User.objects.create_user(
            phone="09123456789", is_staff=True, is_superuser=True
        )
        self.staff = User.objects.create_user(phone="09123456780", is_staff=True)
        self.factory = APIRequestFactory()

    def row(self, size="M", color="سفید", **overrides):
        return {
            "sku": "",
            "options": {"size": size, "color": color},
            "price": 500,
            "stock": 3,
            "is_active": True,
            **overrides,
        }

    def call(
        self, view, method="get", body=None, purpose="management", user=None, **kwargs
    ):
        request = getattr(self.factory, method)("/", body, format="json")
        force_authenticate(request, user=user or self.admin, token={"purpose": purpose})
        return view.as_view()(request, **kwargs)

    def action(self, action, data, version=None, **kwargs):
        self.item.refresh_from_db()
        return self.call(
            WorkspaceProductView,
            "post",
            {
                "version": version or document(self.item)["version"],
                "action": action,
                "data": data,
            },
            pk=self.item.pk,
            **kwargs,
        )

    def test_create_draft_without_price_or_brand_and_generate_slug(self):
        result = self.call(
            WorkspaceProductView,
            "post",
            {"basic": {"name": "پیراهن جدید", "category_id": self.category.pk}},
        )
        self.assertEqual(result.status_code, 201, result.data)
        self.assertEqual(result.data["status"], "draft")
        self.assertFalse(result.data["is_active"])
        self.assertTrue(result.data["slug"])
        self.assertEqual(result.data["price"], 0)

    def test_combinations_are_cartesian_and_bounded(self):
        self.assertEqual(len(preview_combinations(self.axes)), 4)
        axes = [
            dict(
                key="a", label="الف", values=[str(i) for i in range(21)], required=True
            ),
            dict(key="b", label="ب", values=[str(i) for i in range(10)], required=True),
        ]
        with self.assertRaises(ValidationError):
            preview_combinations(axes)

    def test_batch_keeps_independent_prices_and_assigns_unique_skus(self):
        item = save_combinations(
            self.item.pk, 1, self.axes, [self.row(), self.row("L", "مشکی", price=600)]
        )
        variants = list(item.variants.order_by("pk"))
        self.assertEqual([v.price for v in variants], [500, 600])
        self.assertEqual(len({v.sku for v in variants}), 2)
        self.assertTrue(all(v.sku for v in variants))

    def test_invalid_later_row_rolls_back_schema_and_earlier_rows(self):
        with self.assertRaises(ValidationError):
            save_combinations(
                self.item.pk, 1, self.axes, [self.row(), self.row("L", price=0)]
            )
        self.item.refresh_from_db()
        self.assertEqual(self.item.variant_schema, [])
        self.assertEqual(self.item.catalog_revision, 1)
        self.assertFalse(self.item.variants.exists())

    def test_duplicate_options_roll_back_whole_batch(self):
        with self.assertRaises(ValidationError):
            save_combinations(self.item.pk, 1, self.axes, [self.row(), self.row()])
        self.assertFalse(self.item.variants.exists())

    def test_stock_changed_by_checkout_cannot_be_overwritten(self):
        item = save_combinations(self.item.pk, 1, self.axes, [self.row()])
        variant = item.variants.get()
        ProductVariant.objects.filter(pk=variant.pk).update(stock=2)
        row = self.row()
        row.update(id=variant.pk, sku=variant.sku, expected_stock=3, stock=20)
        with self.assertRaises(ValidationError):
            save_combinations(item.pk, item.catalog_revision, self.axes, [row])
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 2)

    def test_existing_identity_and_omitted_rows_are_preserved(self):
        item = save_combinations(
            self.item.pk, 1, self.axes, [self.row(), self.row("L")]
        )
        first, other = list(item.variants.order_by("pk"))
        row = self.row()
        row.update(id=first.pk, sku=first.sku, expected_stock=3, price=700)
        save_combinations(item.pk, item.catalog_revision, self.axes, [row])
        first.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(first.price, 700)
        self.assertEqual(other.stock, 3)
        self.assertEqual(item.variants.count(), 2)

    def test_existing_sku_cannot_change_its_selection(self):
        item = save_combinations(self.item.pk, 1, self.axes, [self.row()])
        variant = item.variants.get()
        row = self.row("L")
        row.update(id=variant.pk, sku=variant.sku, expected_stock=3)
        with self.assertRaises(ValidationError):
            save_combinations(item.pk, item.catalog_revision, self.axes, [row])

    def test_simple_stock_requires_original_value(self):
        with self.assertRaises(ValidationError):
            save_simple(self.item.pk, 1, dict(price=120, stock=5, expected_stock=3))
        save_simple(self.item.pk, 1, dict(price=120, stock=0, expected_stock=4))
        self.item.refresh_from_db()
        self.assertEqual(self.item.stock, 0)

    def test_variant_product_cannot_switch_to_simple(self):
        item = save_combinations(self.item.pk, 1, self.axes, [self.row()])
        with self.assertRaises(ValidationError):
            save_simple(
                item.pk,
                item.catalog_revision,
                dict(price=500, stock=100, expected_stock=4),
            )

    def test_brand_name_only_and_stable_slug_on_rename(self):
        brand = save_brand({"name": "نمونه"})
        slug = brand.slug
        updated = save_brand({"name": "نام جدید"}, brand.pk)
        self.assertEqual(updated.slug, slug)
        with self.assertRaises(ValidationError):
            save_brand({"name": 123})

    def test_change_category_does_not_discard_specs(self):
        attr = Attribute.objects.create(name="جنس", slug="fabric")
        CategoryAttribute.objects.create(category=self.category, attribute=attr)
        ProductAttributeValue.objects.create(
            product=self.item, attribute=attr, value="پنبه"
        )
        other = Category(name="دیگر", slug="other")
        Category.objects.bulk_create([other])
        with self.assertRaises(ValidationError):
            save_basic({"category_id": other.pk}, self.item.pk, 1)
        self.item.refresh_from_db()
        self.assertEqual(self.item.category_id, self.category.pk)

    def test_readiness_prevents_publication_but_zero_stock_allowed(self):
        response = self.action("publication", "published")
        self.assertEqual(response.status_code, 400, response.data)
        from products.models import ProductImage

        ProductImage.objects.create(
            product=self.item, image="tests/shirt.webp", is_primary=True
        )
        Product.objects.filter(pk=self.item.pk).update(stock=0)
        response = self.action("publication", "published")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["is_active"])

    def test_legacy_stock_or_basic_edits_invalidate_workspace_version(self):
        old = document(self.item)["version"]
        Product.objects.filter(pk=self.item.pk).update(stock=3)
        response = self.action("basic", {"name": "جدید"}, version=old)
        self.assertEqual(response.status_code, 400, response.data)
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "پیراهن")

    def test_uploading_image_does_not_invalidate_text_edit_version(self):
        old = document(self.item)["version"]
        from products.models import ProductImage

        ProductImage.objects.create(
            product=self.item, image="test.webp", is_primary=True
        )
        self.assertEqual(document(self.item)["version"], old)

    def test_real_owner_base_allows_catalog_writes(self):
        response = self.call(
            AttributeDefinitionsView,
            "post",
            dict(name="وزن", value_type="number", unit="گرم", choices=[]),
        )
        self.assertEqual(response.status_code, 201, response.data)
        response = self.call(
            ProductCatalogView,
            "post",
            dict(revision=1, action="axes", data=self.axes),
            pk=self.item.pk,
        )
        self.assertEqual(response.status_code, 200, response.data)

    def test_bulk_api_rolls_back_on_unique_sku_conflict(self):
        row1 = self.row()
        row1["sku"] = "SAME"
        row2 = self.row("L")
        row2["sku"] = "SAME"
        response = self.action(
            "combinations", {"axes": self.axes, "rows": [row1, row2]}
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(self.item.variants.exists())
        self.item.refresh_from_db()
        self.assertEqual(self.item.variant_schema, [])

    def test_non_manager_and_unprivileged_staff_cannot_write(self):
        self.assertEqual(
            self.action("basic", {"name": "x"}, purpose="customer").status_code, 403
        )
        self.assertEqual(
            self.action("basic", {"name": "x"}, user=self.staff).status_code, 403
        )
        self.assertEqual(
            self.call(
                CombinationPreviewView, "post", {"axes": self.axes}, user=self.staff
            ).status_code,
            403,
        )

    def test_choices_return_permissions_and_optional_brands(self):
        response = self.call(WorkspaceChoicesView)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["permissions"]["add_product"])
        self.assertEqual(response.data["categories"][0]["id"], self.category.pk)

    def test_inline_brand_creation_uses_real_permission_and_http_post(self):
        response = self.call(WorkspaceBrandView, "post", {"name": "تست"})
        self.assertEqual(response.status_code, 201, response.data)
        response = self.call(
            WorkspaceBrandView, "post", {"name": "بدون مجوز"}, user=self.staff
        )
        self.assertEqual(response.status_code, 403)

    def test_malformed_body_is_validation_error(self):
        response = self.call(WorkspaceProductView, "post", [], pk=self.item.pk)
        self.assertEqual(response.status_code, 400)
        response = self.call(
            WorkspaceProductView, "post", {"basic": {"name": "x", "category_id": True}}
        )
        self.assertEqual(response.status_code, 400)

    def test_hide_remains_possible_with_incomplete_old_data(self):
        Product.objects.filter(pk=self.item.pk).update(
            status="published", is_active=True, price=0
        )
        self.item.refresh_from_db()
        item = set_publication(self.item.pk, 1, "hidden")
        self.assertFalse(item.is_active)

    def test_product_list_summary_uses_variant_prices_and_stock(self):
        from dashboard.api.v1.views import summary_data

        item = save_combinations(
            self.item.pk, 1, self.axes, [self.row(), self.row("L", price=600)]
        )
        result = summary_data("products", item)["catalog_summary"]
        self.assertEqual(result["min_price"], 500)
        self.assertEqual(result["max_price"], 600)
        self.assertEqual(result["total_stock"], 6)
        self.assertEqual(result["variant_count"], 2)

    def test_incorrect_collection_methods_do_not_raise_server_errors(self):
        self.assertEqual(self.call(WorkspaceProductView).status_code, 405)
        self.assertEqual(
            self.call(WorkspaceBrandView, "put", {"name": "x"}).status_code, 405
        )
        self.assertEqual(
            self.call(WorkspaceBrandView, "post", {"name": "x"}, pk=1).status_code, 405
        )
        self.assertEqual(
            self.call(AttributeDefinitionsView, "put", {}).status_code, 400
        )
