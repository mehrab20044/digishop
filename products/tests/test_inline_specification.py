from django.contrib.auth.models import Permission
from django.test import TestCase

from products.models import Attribute, CategoryAttribute, ProductAttributeValue
from products.tests import test_catalog_workflow as fixtures


class InlineSpecificationTests(TestCase):
    def setUp(self):
        from unittest.mock import patch
        fixtures.CatalogWorkflowTests.setUp(self)
        lock = patch("products.services.inline_specification.category_tree_write_lock", fixtures.test_lock)
        lock.start()
        self.addCleanup(lock.stop)
    call = fixtures.CatalogWorkflowTests.call
    action = fixtures.CatalogWorkflowTests.action

    def definition(self, **changes):
        return {
            "name": "جنس پارچه",
            "value_type": "choice",
            "unit": "",
            "choices": ["پنبه", "کتان"],
            **changes,
        }

    def payload(self, **changes):
        return {
            "definition": self.definition(),
            "value": "پنبه",
            "values": [],
            **changes,
        }

    def test_create_link_and_apply_with_real_owner_view(self):
        response = self.action("inline-specification", self.payload())
        self.assertEqual(response.status_code, 200, response.data)
        attribute = Attribute.objects.get(name="جنس پارچه")
        self.assertEqual(response.data["values"][str(attribute.pk)], "پنبه")
        rule = CategoryAttribute.objects.get(
            category=self.category, attribute=attribute
        )
        self.assertFalse(rule.required)
        self.assertEqual(response.data["schema"][0]["id"], attribute.pk)

    def test_existing_definition_is_reused_without_duplicate(self):
        attribute = Attribute.objects.create(name="جنس", slug="fabric")
        response = self.action(
            "inline-specification",
            {"attribute_id": attribute.pk, "value": "پنبه", "values": []},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Attribute.objects.count(), 1)
        self.assertEqual(
            ProductAttributeValue.objects.get(product=self.item).value, "پنبه"
        )

    def test_invalid_value_rolls_back_definition_rule_and_values(self):
        response = self.action("inline-specification", self.payload(value="پلاستیک"))
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Attribute.objects.filter(name="جنس پارچه").exists())
        self.assertFalse(
            CategoryAttribute.objects.filter(category=self.category).exists()
        )
        self.assertFalse(self.item.attribute_values.exists())
        self.item.refresh_from_db()
        self.assertEqual(self.item.catalog_revision, 1)

    def test_unsaved_other_values_are_saved_together(self):
        existing = Attribute.objects.create(name="کشور", slug="country")
        CategoryAttribute.objects.create(category=self.category, attribute=existing)
        ProductAttributeValue.objects.create(
            product=self.item, attribute=existing, value="قدیمی"
        )
        response = self.action(
            "inline-specification",
            self.payload(values=[{"attribute_id": existing.pk, "value": "ایران"}]),
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            ProductAttributeValue.objects.get(
                product=self.item, attribute=existing
            ).value,
            "ایران",
        )
        self.assertEqual(self.item.attribute_values.count(), 2)

    def test_duplicate_name_does_not_create_or_change_any_rule(self):
        Attribute.objects.create(name="جنس پارچه", slug="fabric")
        response = self.action("inline-specification", self.payload())
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(self.item.attribute_values.exists())
        self.assertFalse(
            CategoryAttribute.objects.filter(category=self.category).exists()
        )

    def test_no_category_permission_cannot_attach_attribute(self):
        required = [
            "view_product",
            "change_product",
            "view_category",
            "view_attribute",
            "add_attribute",
            "add_productattributevalue",
            "change_productattributevalue",
            "delete_productattributevalue",
            "add_categoryattribute",
        ]
        self.staff.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="products", codename__in=required
            )
        )
        response = self.action("inline-specification", self.payload(), user=self.staff)
        self.assertEqual(response.status_code, 403, response.data)
        self.assertFalse(Attribute.objects.filter(name="جنس پارچه").exists())

    def test_missing_or_ambiguous_definition_is_rejected(self):
        for data in [
            self.payload(value=""),
            self.payload(attribute_id=1),
            {"value": "x", "values": []},
        ]:
            with self.subTest(data=data):
                self.assertEqual(
                    self.action("inline-specification", data).status_code, 400
                )

    def test_unknown_preexisting_values_cannot_be_injected(self):
        foreign = Attribute.objects.create(name="غیرمجاز", slug="invalid")
        response = self.action(
            "inline-specification",
            self.payload(values=[{"attribute_id": foreign.pk, "value": "x"}]),
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Attribute.objects.filter(name="جنس پارچه").exists())
