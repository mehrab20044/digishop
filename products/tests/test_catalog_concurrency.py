from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from products.models import Category, Product
from products.services.attribute_service import save_axes


@skipUnless(connection.vendor == 'postgresql', 'Row-lock concurrency requires PostgreSQL')
class CatalogConcurrencyTests(TransactionTestCase):
    def test_two_editors_cannot_overwrite_each_others_schema(self):
        category = Category.objects.create(name='کفش', slug='shoes')
        product = Product.objects.create(name='کفش', slug='shoe', category=category, price=100, status='draft', is_active=False)
        barrier = Barrier(2)

        def writer(label):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    save_axes(product.pk, 1, [{'key': 'size', 'label': label, 'values': ['40'], 'required': True}])
                    return 'saved'
                except ValidationError:
                    return 'stale'
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(writer, ['A', 'B']))
        self.assertCountEqual(outcomes, ['saved', 'stale'])
        product.refresh_from_db()
        self.assertEqual(product.catalog_revision, 2)
