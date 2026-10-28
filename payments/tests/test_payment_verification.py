from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Address
from cart.models import Cart, CartItem
from orders.models import Order, StoreSettings
from orders.services.order_service import cancel_order, create_order
from payments.gateways.base import (
    VerificationResult,
    VerificationStatus,
)
from payments.models import FakeGatewaySession, Payment
from payments.services.fake_payment_service import verify_fake_payment
from payments.services.payment_service import start_payment
from products.models import Category, Product

User = get_user_model()


@override_settings(DEBUG=True, PAYMENTS_FAKE_ENABLED=True)
class PaymentVerificationTests(TestCase):
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
            name="تست تأیید",
            slug="verification-category",
        )
        self.product = Product.objects.create(
            category=category,
            name="محصول آزمایشی",
            slug="verification-product",
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
        self.payment = start_payment(
            self.user,
            order_id=self.order.pk,
            request_id=uuid4(),
        ).payment

    def assert_mismatch_is_not_paid(self, **overrides):
        response = {
            "status": VerificationStatus.SUCCEEDED,
            "authority": self.payment.authority,
            "reference_id": str(uuid4()),
            "amount": self.payment.amount,
            "currency": self.payment.currency,
        }
        response.update(overrides)

        with patch(
            "payments.services.fake_payment_service.FakeGateway.verify",
            return_value=VerificationResult(**response),
        ):
            result = verify_fake_payment(
                self.user,
                payment_id=self.payment.pk,
            )

        self.assertEqual(
            result.status,
            Payment.Status.REVIEW_REQUIRED,
        )
        self.assertEqual(
            result.failure_code,
            "verification_mismatch",
        )
        self.assertIsNone(result.verified_at)

        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PENDING_PAYMENT,
        )
        self.assertIsNone(self.order.paid_at)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_wrong_amount_is_not_accepted(self):
        self.assert_mismatch_is_not_paid(amount=1)

    def test_wrong_currency_is_not_accepted(self):
        self.assert_mismatch_is_not_paid(currency="IRR")

    def test_wrong_authority_is_not_accepted(self):
        self.assert_mismatch_is_not_paid(
            authority=str(uuid4()),
        )

    def test_missing_reference_is_not_accepted(self):
        self.assert_mismatch_is_not_paid(reference_id=None)

    def test_unknown_result_blocks_new_attempt(self):
        response = VerificationResult(
            status=VerificationStatus.UNKNOWN,
            error_code="gateway_timeout",
        )

        with patch(
            "payments.services.fake_payment_service.FakeGateway.verify",
            return_value=response,
        ):
            result = verify_fake_payment(
                self.user,
                payment_id=self.payment.pk,
            )

        self.assertEqual(
            result.status,
            Payment.Status.REVIEW_REQUIRED,
        )
        self.assertEqual(result.failure_code, "gateway_timeout")

        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            start_payment(
                self.user,
                order_id=self.order.pk,
                request_id=uuid4(),
            )

        self.assertEqual(Payment.objects.count(), 1)
        self.order.refresh_from_db()
        self.assertEqual(
            self.order.status,
            Order.Status.PENDING_PAYMENT,
        )

    def record_gateway_success(self):
        reference_id = uuid4()

        FakeGatewaySession.objects.filter(
            payment=self.payment,
        ).update(
            status=FakeGatewaySession.Status.SUCCEEDED,
            reference_id=reference_id,
            decided_at=timezone.now(),
        )

        return str(reference_id)

    def test_late_success_preserves_receipt_without_reviving_order(self):
        now = timezone.now()
        created_at = now - timedelta(hours=3)
        expires_at = now - timedelta(hours=1)

        Order.objects.filter(pk=self.order.pk).update(
            created_at=created_at,
            expires_at=expires_at,
        )
        Payment.objects.filter(pk=self.payment.pk).update(
            created_at=created_at,
            expires_at=expires_at,
        )
        FakeGatewaySession.objects.filter(
            payment=self.payment,
        ).update(
            created_at=created_at,
            expires_at=expires_at,
        )
        reference_id = self.record_gateway_success()

        result = verify_fake_payment(
            self.user,
            payment_id=self.payment.pk,
        )

        self.assertEqual(
            result.status,
            Payment.Status.REVIEW_REQUIRED,
        )
        self.assertEqual(
            result.failure_code,
            "verified_after_deadline",
        )
        self.assertEqual(result.reference_id, reference_id)
        self.assertIsNotNone(result.verified_at)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.EXPIRED)
        self.assertIsNone(self.order.paid_at)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

        # Rechecking must not release stock a second time.
        verify_fake_payment(
            self.user,
            payment_id=self.payment.pk,
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_success_for_cancelled_order_requires_review(self):
        cancel_order(self.user, order_id=self.order.pk)
        reference_id = self.record_gateway_success()

        result = verify_fake_payment(
            self.user,
            payment_id=self.payment.pk,
        )

        self.assertEqual(
            result.status,
            Payment.Status.REVIEW_REQUIRED,
        )
        self.assertEqual(result.failure_code, "order_not_payable")
        self.assertEqual(result.reference_id, reference_id)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertIsNone(self.order.paid_at)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)