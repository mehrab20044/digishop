from contextlib import contextmanager
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from products.models import (
    Attribute,
    Category,
    CategoryAttribute,
    Product,
    ProductAttributeValue,
    ProductVariant,
)
from products.services.attribute_service import (
    effective_rules,
    normalize_value,
    save_axes,
    save_specs,
    save_variant,
    validate_options,
)


@contextmanager
def sqlite_test_lock():
    with transaction.atomic():
        yield


class CatalogConfigurationTests(TestCase):
    def setUp(self):
        # Bulk setup bypasses the PostgreSQL-only category URL lock in SQLite unit tests.
        self.parent = Category(name='پوشاک', slug='clothing')
        Category.objects.bulk_create([self.parent])
        self.child = Category(name='پیراهن', slug='shirts', parent=self.parent)
        Category.objects.bulk_create([self.child])
        self.product = Product.objects.create(name='پیراهن', slug='shirt', category=self.child, price=100, stock=5, status='draft', is_active=False)
        self.lock = patch('products.services.attribute_service.category_tree_write_lock', sqlite_test_lock)
        self.lock.start()
        self.addCleanup(self.lock.stop)
        self.tree_lock = patch('products.services.category_service.category_tree_write_lock', sqlite_test_lock)
        self.tree_lock.start()
        self.addCleanup(self.tree_lock.stop)
        self.axes = [{'key': 'size', 'label': 'سایز', 'values': ['S', 'M'], 'required': True}]

    def version(self):
        self.product.refresh_from_db()
        return self.product.catalog_revision

    def configure(self):
        save_axes(self.product.pk, self.version(), self.axes)

    def variant(self, **changes):
        save_variant(self.product.pk, self.version(), {'sku': 'SHIRT-S', 'options': {'size': 'S'}, 'price': 100, 'stock': 5, 'is_active': True, **changes})
        return self.product.variants.latest('pk')

    def test_inheritance_and_local_override(self):
        attr = Attribute.objects.create(name='جنس', slug='material')
        CategoryAttribute.objects.create(category=self.parent, attribute=attr, required=True)
        self.assertTrue(effective_rules(self.child.pk)[attr.pk].required)
        CategoryAttribute.objects.create(category=self.child, attribute=attr, required=False)
        self.assertFalse(effective_rules(self.child.pk)[attr.pk].required)

    def test_related_categories_do_not_leak(self):
        other = Category(name='غذا', slug='food')
        Category.objects.bulk_create([other])
        self.child.related_categories.add(other)
        attr = Attribute.objects.create(name='کالری', slug='calories')
        CategoryAttribute.objects.create(category=other, attribute=attr)
        self.assertNotIn(attr.pk, effective_rules(self.child.pk))

    def test_number_normalization_and_invalid_numbers(self):
        attr = Attribute(name='وزن', slug='weight', value_type='number')
        self.assertEqual(normalize_value(attr, '۱۲.۵۰'), '12.5')
        self.assertEqual(normalize_value(attr, '100'), '100')
        for value in ['nan', 'Infinity', '12kg', '1e1000', '0.000000001']:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                normalize_value(attr, value)

    def test_boolean_and_choice_values(self):
        boolean = Attribute(name='ضدآب', value_type='boolean')
        choice = Attribute(name='جنس', value_type='choice', choices=['پنبه', 'کتان'])
        self.assertEqual(normalize_value(boolean, 'بله'), 'بله')
        self.assertEqual(normalize_value(choice, 'پنبه'), 'پنبه')
        for attr, value in [(boolean, 'شاید'), (choice, 'پشم')]:
            with self.assertRaises(ValidationError):
                normalize_value(attr, value)

    def test_definition_change_validates_existing_values(self):
        attr = Attribute.objects.create(name='جنس', slug='material')
        ProductAttributeValue.objects.create(product=self.product, attribute=attr, value='پنبه')
        attr.value_type = 'number'
        with self.assertRaises(ValidationError):
            attr.full_clean()

    def test_required_specs_checked_before_publication(self):
        attr = Attribute.objects.create(name='جنس', slug='material')
        CategoryAttribute.objects.create(category=self.parent, attribute=attr, required=True)
        save_specs(self.product.pk, self.version(), [])
        self.product.status = 'published'
        with self.assertRaises(ValidationError):
            self.product.full_clean()
        self.product.refresh_from_db()
        save_specs(self.product.pk, self.version(), [{'attribute_id': attr.pk, 'value': 'پنبه'}])
        self.product.refresh_from_db()
        self.product.status = 'published'
        self.product.full_clean()

    def test_unknown_and_duplicate_specs_rejected_atomically(self):
        attr = Attribute.objects.create(name='وزن', slug='weight')
        with self.assertRaises(ValidationError):
            save_specs(self.product.pk, self.version(), [{'attribute_id': attr.pk, 'value': '10'}])
        CategoryAttribute.objects.create(category=self.child, attribute=attr)
        with self.assertRaises(ValidationError):
            save_specs(self.product.pk, self.version(), [{'attribute_id': attr.pk, 'value': '10'}, {'attribute_id': attr.pk, 'value': '11'}])
        self.assertFalse(self.product.attribute_values.exists())

    def test_generic_variant(self):
        self.configure()
        variant = self.variant()
        self.assertEqual(variant.display_name, 'سایز: S')
        self.assertEqual((variant.price, variant.stock), (100, 5))

    def test_options_canonical_order_unique(self):
        save_axes(self.product.pk, self.version(), self.axes + [{'key': 'fabric', 'label': 'جنس', 'values': ['پنبه'], 'required': True}])
        self.variant(options={'size': 'S', 'fabric': 'پنبه'})
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.variant(sku='OTHER', options={'fabric': 'پنبه', 'size': 'S'})
        self.assertEqual(self.product.variants.count(), 1)

    def test_invalid_options(self):
        for options in [{}, {'color': 'red'}, {'size': 'XL'}, {'size': 2}]:
            with self.subTest(options=options), self.assertRaises(ValidationError):
                validate_options(self.axes, options)

    def test_schema_change_does_not_invalidate_variants(self):
        self.configure()
        self.variant()
        with self.assertRaises(ValidationError):
            save_axes(self.product.pk, self.version(), [dict(self.axes[0], values=['M'])])
        self.product.refresh_from_db()
        self.assertEqual(self.product.variant_schema, self.axes)

    def test_stale_revision(self):
        version = self.version()
        self.configure()
        with self.assertRaises(ValidationError):
            save_axes(self.product.pk, version, [])

    def test_stale_stock_not_restored(self):
        self.configure()
        variant = self.variant()
        ProductVariant.objects.filter(pk=variant.pk).update(stock=4)
        with self.assertRaises(ValidationError):
            save_variant(self.product.pk, self.version(), {'sku': variant.sku, 'options': variant.options, 'price': 120, 'stock': 5, 'expected_stock': 5, 'is_active': True}, variant.pk)
        variant.refresh_from_db()
        self.assertEqual((variant.stock, variant.price), (4, 100))

    def test_update_preserves_variant_id(self):
        self.configure()
        variant = self.variant()
        save_variant(self.product.pk, self.version(), {'sku': variant.sku, 'options': {'size': 'M'}, 'price': 120, 'stock': 3, 'expected_stock': 5, 'is_active': False}, variant.pk)
        variant.refresh_from_db()
        self.assertEqual(variant.options, {'size': 'M'})
        self.assertFalse(variant.is_active)
        self.assertEqual(self.product.variants.count(), 1)

    def test_legacy_labels_and_constraint(self):
        variant = ProductVariant.objects.create(product=self.product, sku='OLD1', color='Blue', storage='128GB', price=100, stock=1)
        self.assertEqual(variant.display_name, 'Blue / 128GB')
        variant.options = {'color': 'Blue', 'storage': '128GB'}
        self.assertEqual(variant.display_name, 'Blue / 128GB')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductVariant.objects.create(product=self.product, sku='OLD2', color='Blue', storage='128GB', price=200, stock=1)

    def test_sku_unique_and_price_positive(self):
        self.configure()
        self.variant()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.variant(options={'size': 'M'})
        with self.assertRaises(ValidationError):
            self.variant(sku='SECOND', options={'size': 'M'}, price=0)

    def test_generic_color_size_pairs_do_not_hit_legacy_constraint(self):
        axes = self.axes + [{'key': 'color', 'label': 'رنگ', 'values': ['Blue'], 'required': True}]
        save_axes(self.product.pk, self.version(), axes)
        first = self.variant(sku='S-BLUE', options={'size': 'S', 'color': 'Blue'})
        second = self.variant(sku='M-BLUE', options={'size': 'M', 'color': 'Blue'})
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(self.product.variants.count(), 2)
