from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Address
from cart.models import Cart, CartItem
from orders.models import Order, StoreSettings
from orders.services.order_service import create_order
from payments.models import FakeGatewaySession, Payment
from payments.services.payment_service import start_payment
from products.models import Category, Product

User = get_user_model()


@override_settings(DEBUG=True, PAYMENTS_FAKE_ENABLED=True)
class PaymentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
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
            name="تست API پرداخت",
            slug="payment-api-category",
        )
        self.product = Product.objects.create(
            category=category,
            name="محصول آزمایشی",
            slug="payment-api-product",
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
        self.start_url = reverse("payments:start")
        self.client.force_authenticate(user=self.user)

    def make_payment(self):
        return start_payment(
            self.user,
            order_id=self.order.pk,
            request_id=uuid4(),
        ).payment

    def payment_url(self, name, payment):
        return reverse(
            f"payments:{name}",
            kwargs={"pk": payment.pk},
        )

    def test_start_uses_server_amount_and_gateway(self):
        response = self.client.post(
            self.start_url,
            {
                "order_id": str(self.order.pk),
                "request_id": str(uuid4()),
                "amount": 1,
                "currency": "IRR",
                "gateway": "other",
                "status": "succeeded",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        payment = response.data["payment"]
        self.assertEqual(payment["amount"], 250000)
        self.assertEqual(payment["currency"], "IRT")
        self.assertEqual(payment["gateway"], "fake")
        self.assertEqual(payment["status"], "pending")
        self.assertEqual(
            response.data["redirect_url"],
            f"/payments/fake/{payment['id']}",
        )
        self.assertNotIn("authority", payment)
        self.assertNotIn("failure_code", payment)

    def test_duplicate_start_returns_same_payment(self):
        payload = {
            "order_id": str(self.order.pk),
            "request_id": str(uuid4()),
        }

        first = self.client.post(
            self.start_url,
            payload,
            format="json",
        )
        second = self.client.post(
            self.start_url,
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            first.data["payment"]["id"],
            second.data["payment"]["id"],
        )
        self.assertEqual(Payment.objects.count(), 1)

    def test_anonymous_requests_are_rejected(self):
        payment = self.make_payment()
        self.client.force_authenticate(user=None)

        requests = (
            ("post", self.start_url, {
                "order_id": str(self.order.pk),
                "request_id": str(uuid4()),
            }),
            ("get", self.payment_url("detail", payment), None),
            ("get", self.payment_url("fake-page", payment), None),
            (
                "post",
                self.payment_url("fake-decision", payment),
                {"outcome": "success"},
            ),
            ("post", self.payment_url("fake-verify", payment), {}),
        )

        for method, url, payload in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(
                    url,
                    data=payload,
                    format="json",
                )
                self.assertEqual(response.status_code, 401)

    def test_other_user_cannot_access_payment(self):
        payment = self.make_payment()
        self.client.force_authenticate(user=self.other_user)

        requests = (
            ("post", self.start_url, {
                "order_id": str(self.order.pk),
                "request_id": str(uuid4()),
            }),
            ("get", self.payment_url("detail", payment), None),
            ("get", self.payment_url("fake-page", payment), None),
            (
                "post",
                self.payment_url("fake-decision", payment),
                {"outcome": "success"},
            ),
            ("post", self.payment_url("fake-verify", payment), {}),
        )

        for method, url, payload in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(
                    url,
                    data=payload,
                    format="json",
                )
                self.assertEqual(response.status_code, 404)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)

    def test_get_fake_page_does_not_complete_payment(self):
        payment = self.make_payment()

        response = self.client.get(
            self.payment_url("fake-page", payment),
            {"outcome": "success"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_test"])
        self.assertTrue(response.data["can_decide"])

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)

    def test_success_updates_payment_and_order(self):
        payment = self.make_payment()

        response = self.client.post(
            self.payment_url("fake-decision", payment),
            {"outcome": "success"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "succeeded")
        self.assertIsNotNone(response.data["reference_id"])

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

        page = self.client.get(
            self.payment_url("fake-page", payment),
        )
        self.assertFalse(page.data["can_decide"])

    def test_cancel_attempt_keeps_order_payable(self):
        payment = self.make_payment()

        response = self.client.post(
            self.payment_url("fake-decision", payment),
            {"outcome": "cancel"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "cancelled")

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_verify_pending_payment_does_not_mark_it_successful(self):
        payment = self.make_payment()

        response = self.client.post(
            self.payment_url("fake-verify", payment),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "pending")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING_PAYMENT)

    def test_invalid_decision_is_rejected(self):
        payment = self.make_payment()

        response = self.client.post(
            self.payment_url("fake-decision", payment),
            {"outcome": "paid"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        session = FakeGatewaySession.objects.get(payment=payment)
        self.assertEqual(session.status, FakeGatewaySession.Status.PENDING)

    def test_invalid_start_input_is_rejected(self):
        payloads = (
            {},
            {"order_id": str(self.order.pk)},
            {
                "order_id": "invalid",
                "request_id": str(uuid4()),
            },
            {
                "order_id": str(self.order.pk),
                "request_id": "invalid",
            },
        )

        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    self.start_url,
                    payload,
                    format="json",
                )
                self.assertEqual(response.status_code, 400)

        self.assertFalse(Payment.objects.exists())

    def assert_fake_endpoints_disabled(self, payment):
        requests = (
            ("post", self.start_url, {
                "order_id": str(self.order.pk),
                "request_id": str(uuid4()),
            }),
            ("get", self.payment_url("fake-page", payment), None),
            (
                "post",
                self.payment_url("fake-decision", payment),
                {"outcome": "success"},
            ),
            ("post", self.payment_url("fake-verify", payment), {}),
        )

        for method, url, payload in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(
                    url,
                    data=payload,
                    format="json",
                )
                self.assertEqual(response.status_code, 404)

        # Historical records remain readable by their owner.
        detail = self.client.get(
            self.payment_url("detail", payment),
        )
        self.assertEqual(detail.status_code, 200)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_fake_endpoints_require_explicit_opt_in(self):
        payment = self.make_payment()

        with override_settings(PAYMENTS_FAKE_ENABLED=False):
            self.assert_fake_endpoints_disabled(payment)

    def test_fake_endpoints_are_disabled_without_debug(self):
        payment = self.make_payment()

        with override_settings(DEBUG=False):
            self.assert_fake_endpoints_disabled(payment)