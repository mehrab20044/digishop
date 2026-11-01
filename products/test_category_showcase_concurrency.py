from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from products.models import Category
from products.services.category_showcase_service import (
    StaleSelection,
    home_category_ids,
    set_home_categories,
)


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL advisory locking")
class CategoryShowcaseConcurrencyTests(TransactionTestCase):
    def test_two_editors_with_same_version_cannot_overwrite_each_other(self):
        Category.objects.bulk_create(
            [
                Category(
                    name=f"Concurrency {i}",
                    slug=f"category-concurrency-{i}",
                    image=f"categories/{i}.webp",
                )
                for i in range(6)
            ]
        )
        ids = list(Category.objects.order_by("pk").values_list("pk", flat=True))
        choices = [ids[:5], ids[1:]]
        barrier = Barrier(2)

        def save(selected):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    set_home_categories(selected, [])
                    return (200, selected)
                except StaleSelection:
                    return (409, selected)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(save, choices))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        winner = next(selected for status, selected in results if status == 200)
        self.assertEqual(home_category_ids(), winner)
