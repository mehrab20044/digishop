from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CatalogMigrationTests(TransactionTestCase):
    def test_legacy_variants_keep_identifiers_prices_stocks_and_fields(self):
        executor = MigrationExecutor(connection)
        previous = [('products', '0016_product_gallery_description_html_and_more')]
        target = [('products', '0018_migrate_variant_options')]
        executor.migrate(previous)
        try:
            apps = executor.loader.project_state(previous).apps
            Category = apps.get_model('products', 'Category')
            Product = apps.get_model('products', 'Product')
            Variant = apps.get_model('products', 'ProductVariant')
            category = Category.objects.create(name='گوشی', slug='phones')
            product = Product.objects.create(name='Demo', slug='demo', category=category, price=10, stock=0)
            variant = Variant.objects.create(product=product, sku='OLD-1', color='Blue', storage='128GB', price=100, stock=7)
            product_id, variant_id = product.pk, variant.pk
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            apps = executor.loader.project_state(target).apps
            new = apps.get_model('products', 'ProductVariant').objects.get(pk=variant_id)
            self.assertEqual((new.product_id, new.sku, new.price, new.stock), (product_id, 'OLD-1', 100, 7))
            self.assertEqual(new.options, {'color': 'Blue', 'storage': '128GB'})
            self.assertEqual((new.color, new.storage), ('Blue', '128GB'))
            self.assertTrue(new.combination_key)
            self.assertEqual(len(apps.get_model('products', 'Product').objects.get(pk=product_id).variant_schema), 2)
        finally:
            MigrationExecutor(connection).migrate(target)
