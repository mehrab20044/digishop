from datetime import timedelta
from io import StringIO
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from accounts.models import Address
from cart.models import Cart, CartItem
from orders.models import Order, StoreSettings
from orders.services.order_service import create_order
from products.models import Category, Product

User = get_user_model()


class ExpireOrdersCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="09120000001",
            first_name="مهراب",
            last_name="محمدی",
            phone_verified_at=timezone.now(),
        )
        self.address = Address.objects.create(
            user=self.user,
            recipient_name="مهراب محمدی",
            recipient_phone=self.user.phone,
            province="قزوین",
            city="محمدیه",
            street_address="خیابان آزمایش",
            building_number="1",
            postal_code="1234567890",
            is_default=True,
        )
        StoreSettings.objects.create(shipping_cost=50000)

        category = Category.objects.create(
            name="تست فرمان",
            slug="command-test-category",
        )
        self.product = Product.objects.create(
            category=category,
            name="محصول آزمایشی",
            slug="command-test-product",
            price=100000,
            stock=10,
            is_active=True,
            status=Product.Status.PUBLISHED,
        )
        self.cart = Cart.objects.create(user=self.user)

    def make_order(self, *, expired=False):
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            selection_key=f"p:{self.product.pk}:v:0",
            product_name=self.product.name,
            quantity=1,
            price_seen=self.product.price,
        )
        order, _ = create_order(
            self.user,
            address_id=self.address.pk,
            request_id=uuid4(),
        )

        if expired:
            now = timezone.now()
            Order.objects.filter(pk=order.pk).update(
                created_at=now - timedelta(hours=3),
                expires_at=now - timedelta(hours=1),
            )

        return order

    def run_command(self, **options):
        output = StringIO()
        call_command("expire_orders", stdout=output, **options)
        return output.getvalue()

    def test_empty_database_is_handled(self):
        output = self.run_command()

        self.assertIn(
            "Processed 0 orders; expired 0 orders.",
            output,
        )

    def test_expired_orders_are_processed_across_batches(self):
        expired_orders = [
            self.make_order(expired=True)
            for _ in range(3)
        ]
        pending_order = self.make_order()

        output = self.run_command(batch_size=1)

        self.assertIn(
            "Processed 3 orders; expired 3 orders.",
            output,
        )

        for order in expired_orders:
            order.refresh_from_db()
            self.assertEqual(order.status, Order.Status.EXPIRED)
            self.assertIsNotNone(order.expired_at)

        pending_order.refresh_from_db()
        self.assertEqual(
            pending_order.status,
            Order.Status.PENDING_PAYMENT,
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

        # A second execution must not release stock again.
        second_output = self.run_command(batch_size=1)

        self.assertIn(
            "Processed 0 orders; expired 0 orders.",
            second_output,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

    def test_paid_order_is_not_expired(self):
        order = self.make_order(expired=True)
        Order.objects.filter(pk=order.pk).update(
            status=Order.Status.PAID,
            paid_at=timezone.now(),
        )

        output = self.run_command()

        self.assertIn(
            "Processed 0 orders; expired 0 orders.",
            output,
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)

    def test_invalid_batch_size_is_rejected(self):
        for batch_size in (0, -1, 2001):
            with self.subTest(batch_size=batch_size):
                with self.assertRaises(CommandError):
                    self.run_command(batch_size=batch_size)