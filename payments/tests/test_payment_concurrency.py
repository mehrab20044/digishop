from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase, override_settings
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
from payments.models import FakeGatewaySession, Payment
from payments.services.fake_payment_service import (
    decide_fake_payment,
    verify_fake_payment,
)
from payments.services.payment_service import start_payment
from products.models import Category, Product

User = get_user_model()


@skipUnless(
    connection.vendor == "postgresql",
    "These concurrency tests require PostgreSQL.",
)
@override_settings(DEBUG=True, PAYMENTS_FAKE_ENABLED=True)
class PaymentConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="09120000001",
            first_name="مهراب",
            last_name="محمدی",
            phone_verified_at=timezone.now(),
        )
        address = Address.objects.create(
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
            name="تست هم‌زمانی پرداخت",
            slug="payment-concurrency-category",
        )
        self.product = Product.objects.create(
            category=category,
            name="محصول آزمایشی",
            slug="payment-concurrency-product",
            price=100000,
            stock=5,
            is_active=True,
            status=Product.Status.PUBLISHED,
        )
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            selection_key=f"p:{self.product.pk}:v:0",
            product_name=self.product.name,
            quantity=2,
            price_seen=100000,
        )
        self.order, _ = create_order(
            self.user,
            address_id=address.pk,
            request_id=uuid4(),
            expected_total=250000,
        )

    def run_concurrently(self, first_action, second_action):
        barrier = Barrier(2)

        def worker(action):
            close_old_connections()

            try:
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

    def current_user(self):
        return User.objects.get(pk=self.user.pk)

    def make_payment(self):
        return start_payment(
            self.user,
            order_id=self.order.pk,
            request_id=uuid4(),
        ).payment

    def test_simultaneous_start_creates_one_active_payment(self):
        def start():
            result = start_payment(
                self.current_user(),
                order_id=self.order.pk,
                request_id=uuid4(),
            )
            return str(result.payment.pk), result.created

        results = self.run_concurrently(start, start)

        self.assertEqual(results[0][0], results[1][0])
        self.assertCountEqual(
            [result[1] for result in results],
            [True, False],
        )
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(FakeGatewaySession.objects.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_simultaneous_success_is_applied_once(self):
        payment = self.make_payment()

        def succeed():
            result = decide_fake_payment(
                self.current_user(),
                payment_id=payment.pk,
                outcome="success",
            )
            return result.status, result.reference_id

        results = self.run_concurrently(succeed, succeed)

        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0], Payment.Status.SUCCEEDED)
        self.assertIsNotNone(results[0][1])

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertIsNotNone(self.order.paid_at)

        self.assertEqual(
            Payment.objects.filter(
                status=Payment.Status.SUCCEEDED,
            ).count(),
            1,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_payment_and_cancellation_cannot_both_win(self):
        payment = self.make_payment()

        def succeed():
            result = decide_fake_payment(
                self.current_user(),
                payment_id=payment.pk,
                outcome="success",
            )
            return result.status

        def cancel():
            try:
                result = cancel_order(
                    self.current_user(),
                    order_id=self.order.pk,
                )
            except ValidationError:
                return "rejected"

            return result.status

        self.run_concurrently(succeed, cancel)

        self.order.refresh_from_db()
        payment.refresh_from_db()
        self.product.refresh_from_db()

        if self.order.status == Order.Status.PAID:
            self.assertEqual(
                payment.status,
                Payment.Status.SUCCEEDED,
            )
            self.assertIsNotNone(self.order.paid_at)
            self.assertEqual(self.product.stock, 3)
        else:
            self.assertEqual(
                self.order.status,
                Order.Status.CANCELLED,
            )
            self.assertEqual(
                payment.status,
                Payment.Status.CANCELLED,
            )
            self.assertIsNone(self.order.paid_at)
            self.assertEqual(self.product.stock, 5)

    def test_expiration_and_late_verification_release_stock_once(self):
        payment = self.make_payment()
        now = timezone.now()
        created_at = now - timedelta(hours=3)
        expires_at = now - timedelta(hours=1)

        Order.objects.filter(pk=self.order.pk).update(
            created_at=created_at,
            expires_at=expires_at,
        )
        Payment.objects.filter(pk=payment.pk).update(
            created_at=created_at,
            expires_at=expires_at,
        )
        reference_id = uuid4()

        # Simulate a gateway receipt arriving after the order deadline.
        FakeGatewaySession.objects.filter(payment=payment).update(
            created_at=created_at,
            expires_at=expires_at,
            status=FakeGatewaySession.Status.SUCCEEDED,
            reference_id=reference_id,
            decided_at=now,
        )

        def verify():
            return verify_fake_payment(
                self.current_user(),
                payment_id=payment.pk,
            ).status

        def expire():
            return expire_order(order_id=self.order.pk)

        self.run_concurrently(verify, expire)

        self.order.refresh_from_db()
        payment.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(self.order.status, Order.Status.EXPIRED)
        self.assertIsNone(self.order.paid_at)
        self.assertEqual(
            payment.status,
            Payment.Status.REVIEW_REQUIRED,
        )
        self.assertEqual(payment.reference_id, str(reference_id))
        self.assertIsNotNone(payment.verified_at)
        self.assertEqual(self.product.stock, 5)

        self.assertFalse(expire_order(order_id=self.order.pk))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)