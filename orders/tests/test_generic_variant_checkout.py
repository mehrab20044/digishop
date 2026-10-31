from uuid import uuid4

from django.db import transaction
from django.test import TestCase

from cart.services import add_item
from orders.services.order_service import cancel_order
from orders.tests import test_order_service as fixtures
from products.services.attribute_service import save_axes, save_variant


class GenericVariantCheckoutTests(TestCase):
    setUp = fixtures.OrderServiceTests.setUp
    checkout = fixtures.OrderServiceTests.checkout

    def test_generic_selection_snapshot_reservation_and_cancel(self):
        product = save_axes(self.product.pk, self.product.catalog_revision, [{'key': 'size', 'label': 'سایز', 'values': ['40'], 'required': True}])
        save_variant(product.pk, product.catalog_revision, {'sku': 'GENERIC-40', 'options': {'size': '40'}, 'price': 120000, 'stock': 5, 'is_active': True})
        variant = product.variants.get()
        self.item.delete()
        with transaction.atomic():
            add_item(self.cart, {'product_id': product.pk, 'variant_id': variant.pk, 'quantity': 2, 'request_id': uuid4()})
        self.assertEqual(self.cart.items.get().variant_name, 'سایز: 40')
        order, created = self.checkout()
        self.assertTrue(created)
        self.assertEqual(order.items.get().variant_name, 'سایز: 40')
        self.assertEqual(order.items.get().unit_price, 120000)
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 3)
        cancel_order(self.user, order_id=order.pk)
        variant.refresh_from_db()
        self.assertEqual(variant.stock, 5)
