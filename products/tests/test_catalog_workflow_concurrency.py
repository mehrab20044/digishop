from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from products.models import Category, Product
from products.services.catalog_workflow import save_combinations


@skipUnless(connection.vendor == "postgresql", "Requires actual PostgreSQL row locks")
class CatalogWorkflowConcurrencyTests(TransactionTestCase):
    def test_competing_batches_cannot_duplicate_or_overwrite_skus(self):
        category = Category.objects.create(name="لباس", slug="clothes")
        item = Product.objects.create(
            name="پیراهن",
            slug="shirt",
            category=category,
            price=0,
            stock=0,
            status="draft",
            is_active=False,
        )
        barrier = Barrier(2)
        axes = [dict(key="size", label="سایز", values=["M"], required=True)]

        def writer(price):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    save_combinations(
                        item.pk,
                        1,
                        axes,
                        [
                            dict(
                                sku="",
                                options={"size": "M"},
                                price=price,
                                stock=5,
                                is_active=True,
                            )
                        ],
                    )
                    return "saved"
                except ValidationError:
                    return "stale"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(writer, [500, 600]))
        self.assertCountEqual(outcomes, ["saved", "stale"])
        self.assertEqual(item.variants.count(), 1)
        self.assertIn(item.variants.get().price, [500, 600])
