from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Address
from cart.models import Cart, CartItem
from orders.models import Order, StoreSettings
from orders.services.order_service import (
    cancel_order,
    create_order,
    expire_order,
)
from products.models import Category, Product

User = get_user_model()


@skipUnless(
    connection.vendor == "postgresql",
    "These concurrency tests require PostgreSQL.",
)
class OrderConcurrencyTests(TransactionTestCase):
    def setUp(self):
        StoreSettings.objects.create(shipping_cost=50000)

        category = Category.objects.create(
            name="تست هم‌زمانی",
            slug="concurrency-category",
        )
        self.product = Product.objects.create(
            category=category,
            name="آخرین موجودی",
            slug="last-stock",
            price=100000,
            stock=1,
            is_active=True,
            status=Product.Status.PUBLISHED,
        )

        self.first_user, self.first_address = self.make_customer(
            "09120000001",
        )
        self.second_user, self.second_address = self.make_customer(
            "09120000002",
        )

    def make_customer(self, phone):
        user = User.objects.create_user(
            phone=phone,
            first_name="کاربر",
            last_name="آزمایشی",
            phone_verified_at=timezone.now(),
        )
        address = Address.objects.create(
            user=user,
            recipient_name="کاربر آزمایشی",
            recipient_phone=phone,
            province="قزوین",
            city="محمدیه",
            street_address="خیابان آزمایش",
            building_number="1",
            postal_code="1234567890",
            is_default=True,
        )
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            selection_key=f"p:{self.product.pk}:v:0",
            product_name=self.product.name,
            quantity=1,
            price_seen=self.product.price,
        )

        return user, address

    def run_concurrently(self, first_action, second_action):
        barrier = Barrier(2)

        def worker(action):
            close_old_connections()

            try:
                # Bound database waits so a deadlock or blocked lock fails.
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                    cursor.execute("SET statement_timeout = '10s'")

                barrier.wait(timeout=10)
                return action()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(worker, first_action),
                executor.submit(worker, second_action),
            ]
            return [
                future.result(timeout=20)
                for future in futures
            ]

    def checkout_result(self, user_id, address_id, request_id):
        user = User.objects.get(pk=user_id)

        try:
            order, created = create_order(
                user,
                address_id=address_id,
                request_id=request_id,
            )
        except ValidationError:
            return {
                "result": "rejected",
            }

        return {
            "result": "created" if created else "replayed",
            "order_id": str(order.pk),
        }

    def test_only_one_customer_can_buy_last_stock(self):
        first_request = uuid4()
        second_request = uuid4()

        results = self.run_concurrently(
            lambda: self.checkout_result(
                self.first_user.pk,
                self.first_address.pk,
                first_request,
            ),
            lambda: self.checkout_result(
                self.second_user.pk,
                self.second_address.pk,
                second_request,
            ),
        )

        self.assertCountEqual(
            [result["result"] for result in results],
            ["created", "rejected"],
        )
        self.assertEqual(Order.objects.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)

        # Only the successful customer's cart was cleared.
        self.assertEqual(CartItem.objects.count(), 1)

    def test_simultaneous_duplicate_checkout_creates_one_order(self):
        request_id = uuid4()

        def checkout():
            return self.checkout_result(
                self.first_user.pk,
                self.first_address.pk,
                request_id,
            )

        results = self.run_concurrently(checkout, checkout)

        self.assertCountEqual(
            [result["result"] for result in results],
            ["created", "replayed"],
        )
        self.assertEqual(
            results[0]["order_id"],
            results[1]["order_id"],
        )
        self.assertEqual(Order.objects.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertFalse(
            CartItem.objects.filter(
                cart__user=self.first_user,
            ).exists()
        )

    def test_cancel_and_expire_release_stock_only_once(self):
        order, _ = create_order(
            self.first_user,
            address_id=self.first_address.pk,
            request_id=uuid4(),
        )
        now = timezone.now()

        Order.objects.filter(pk=order.pk).update(
            created_at=now - timedelta(hours=3),
            expires_at=now - timedelta(hours=1),
        )

        def cancel():
            user = User.objects.get(pk=self.first_user.pk)
            result = cancel_order(user, order_id=order.pk)
            return result.status

        def expire():
            return expire_order(order_id=order.pk)

        self.run_concurrently(cancel, expire)

        order.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(order.status, Order.Status.EXPIRED)
        self.assertIsNotNone(order.expired_at)
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(Order.objects.count(), 1)