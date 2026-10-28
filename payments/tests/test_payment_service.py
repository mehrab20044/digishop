from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Address
from cart.models import Cart, CartItem
from orders.models import Order, StoreSettings
from orders.services.order_service import cancel_order, create_order
from payments.gateways.base import GatewayConfigurationError
from payments.models import FakeGatewaySession, Payment
from payments.services.fake_payment_service import (
    decide_fake_payment,
    verify_fake_payment,
)
from payments.services.payment_service import start_payment
from products.models import Category, Product

User = get_user_model()


@override_settings(DEBUG=True, PAYMENTS_FAKE_ENABLED=True)
class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            phone="09120000001",
            first_name="مهراب",
            last_name="محمدی",
            phone_verified_at=timezone.now(),
        )
        self.other_user = User.objects.create_user(
            phone="09120000002",
            first_name="علی",
            last_name="رضایی",
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
            name="تست پرداخت",
            slug="payment-category",
        )
        self.product = Product.objects.create(
            category=category,
            name="محصول آزمایشی",
            slug="payment-product",
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

    def start(self, request_id=None):
        return start_payment(
            self.user,
            order_id=self.order.pk,
            request_id=request_id or uuid4(),
        )

    def assert_reserved_stock(self):
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def move_deadline_to_past(self, payment=None):
        now = timezone.now()
        created_at = now - timedelta(hours=3)
        expires_at = now - timedelta(hours=1)

        Order.objects.filter(pk=self.order.pk).update(
            created_at=created_at,
            expires_at=expires_at,
        )

        if payment is not None:
            Payment.objects.filter(pk=payment.pk).update(
                created_at=created_at,
                expires_at=expires_at,
            )
            FakeGatewaySession.objects.filter(
                payment=payment,
            ).update(
                created_at=created_at,
                expires_at=expires_at,
            )

    def test_start_uses_order_amount_and_deadline(self):
        result = self.start()
        payment = result.payment

        self.assertTrue(result.created)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.amount, 250000)
        self.assertEqual(payment.currency, "IRT")
        self.assertEqual(payment.expires_at, self.order.expires_at)
        self.assertEqual(
            result.redirect_url,
            f"/payments/fake/{payment.pk}",
        )

        session = FakeGatewaySession.objects.get(payment=payment)
        self.assertEqual(str(session.authority), payment.authority)
        self.assertEqual(session.amount, 250000)
        self.assertEqual(session.status, FakeGatewaySession.Status.PENDING)
        self.assert_reserved_stock()

    def test_repeated_start_does_not_create_another_payment(self):
        request_id = uuid4()

        first = self.start(request_id)
        second = self.start(request_id)
        third = self.start()

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertFalse(third.created)
        self.assertEqual(first.payment.pk, second.payment.pk)
        self.assertEqual(first.payment.pk, third.payment.pk)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(FakeGatewaySession.objects.count(), 1)
        self.assert_reserved_stock()

    def test_success_marks_order_paid_without_deducting_stock_again(self):
        payment = self.start().payment

        result = decide_fake_payment(
            self.user,
            payment_id=payment.pk,
            outcome="success",
        )

        self.assertEqual(result.status, Payment.Status.SUCCEEDED)
        self.assertIsNotNone(result.reference_id)
        self.assertIsNotNone(result.verified_at)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.order.paid_at, result.verified_at)
        self.assert_reserved_stock()

    def test_success_can_be_repeated_without_duplicate_effects(self):
        payment = self.start().payment

        first = decide_fake_payment(
            self.user,
            payment_id=payment.pk,
            outcome="success",
        )
        second = decide_fake_payment(
            self.user,
            payment_id=payment.pk,
            outcome="success",
        )
        verified = verify_fake_payment(
            self.user,
            payment_id=payment.pk,
        )

        self.assertEqual(first.reference_id, second.reference_id)
        self.assertEqual(second.reference_id, verified.reference_id)
        self.assertEqual(verified.status, Payment.Status.SUCCEEDED)
        self.assertEqual(Payment.objects.count(), 1)
        self.assert_reserved_stock()

    def test_cancellation_allows_a_new_attempt_within_deadline(self):
        first = self.start().payment

        cancelled = decide_fake_payment(
            self.user,
            payment_id=first.pk,
            outcome="cancel",
        )

        self.assertEqual(cancelled.status, Payment.Status.CANCELLED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)
        self.assert_reserved_stock()

        second = self.start()

        self.assertTrue(second.created)
        self.assertNotEqual(first.pk, second.payment.pk)
        self.assertEqual(second.payment.expires_at, self.order.expires_at)
        self.assertEqual(Payment.objects.count(), 2)

    def test_decision_cannot_be_changed_after_cancellation(self):
        payment = self.start().payment

        decide_fake_payment(
            self.user,
            payment_id=payment.pk,
            outcome="cancel",
        )

        with self.assertRaises(ValidationError):
            decide_fake_payment(
                self.user,
                payment_id=payment.pk,
                outcome="success",
            )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)
        self.assert_reserved_stock()

    def test_other_user_cannot_access_payment_operations(self):
        payment = self.start().payment

        with self.assertRaises(Http404):
            start_payment(
                self.other_user,
                order_id=self.order.pk,
                request_id=uuid4(),
            )

        with self.assertRaises(Http404):
            decide_fake_payment(
                self.other_user,
                payment_id=payment.pk,
                outcome="success",
            )

        with self.assertRaises(Http404):
            verify_fake_payment(
                self.other_user,
                payment_id=payment.pk,
            )

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)
        self.assert_reserved_stock()

    def test_order_cancellation_prevents_payment_success(self):
        payment = self.start().payment
        cancel_order(self.user, order_id=self.order.pk)

        result = decide_fake_payment(
            self.user,
            payment_id=payment.pk,
            outcome="success",
        )

        self.assertEqual(result.status, Payment.Status.CANCELLED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_expired_order_cannot_start_payment(self):
        self.move_deadline_to_past()

        with self.assertRaises(ValidationError):
            self.start()

        self.assertFalse(Payment.objects.exists())

    def test_expired_attempt_releases_stock_and_cannot_succeed(self):
        payment = self.start().payment
        self.move_deadline_to_past(payment)

        result = decide_fake_payment(
            self.user,
            payment_id=payment.pk,
            outcome="success",
        )

        self.assertEqual(result.status, Payment.Status.EXPIRED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.EXPIRED)

        session = FakeGatewaySession.objects.get(payment=payment)
        self.assertEqual(session.status, FakeGatewaySession.Status.PENDING)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

        verify_fake_payment(self.user, payment_id=payment.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_verifying_pending_session_does_not_mark_order_paid(self):
        payment = self.start().payment

        result = verify_fake_payment(
            self.user,
            payment_id=payment.pk,
        )

        self.assertEqual(result.status, Payment.Status.PENDING)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)
        self.assert_reserved_stock()

    def test_invalid_outcome_is_rejected(self):
        payment = self.start().payment

        with self.assertRaises(ValidationError):
            decide_fake_payment(
                self.user,
                payment_id=payment.pk,
                outcome="paid",
            )

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assert_reserved_stock()

    @override_settings(PAYMENTS_FAKE_ENABLED=False)
    def test_fake_gateway_requires_explicit_opt_in(self):
        with self.assertRaises(GatewayConfigurationError):
            self.start()

        self.assertFalse(Payment.objects.exists())

    @override_settings(DEBUG=False)
    def test_fake_gateway_is_disabled_without_debug(self):
        with self.assertRaises(GatewayConfigurationError):
            self.start()

        self.assertFalse(Payment.objects.exists())