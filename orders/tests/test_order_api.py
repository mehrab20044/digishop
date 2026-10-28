from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Address
from cart.models import Cart, CartItem
from orders.models import Order, StoreSettings
from orders.services.order_service import create_order
from products.models import Category, Product

User = get_user_model()


class OrderAPITests(TestCase):
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
        self.address = Address.objects.create(
            user=self.user,
            recipient_name="مهراب محمدی",
            recipient_phone=self.user.phone,
            province="قزوین",
            city="محمدیه",
            street_address="خیابان آزمایش",
            building_number="12",
            postal_code="1234567890",
            is_default=True,
        )
        StoreSettings.objects.create(shipping_cost=50000)

        category = Category.objects.create(
            name="آزمایشی",
            slug="api-test-category",
        )
        self.product = Product.objects.create(
            category=category,
            name="محصول آزمایشی",
            slug="api-test-product",
            price=100000,
            stock=5,
            is_active=True,
            status=Product.Status.PUBLISHED,
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            selection_key=f"p:{self.product.pk}:v:0",
            product_name=self.product.name,
            quantity=2,
            price_seen=self.product.price,
        )
        self.list_url = reverse("orders:list-create")
        self.client.force_authenticate(user=self.user)

    def payload(self, **overrides):
        data = {
            "address_id": self.address.pk,
            "request_id": str(uuid4()),
            "customer_note": "",
            "expected_total": 250000,
        }
        data.update(overrides)
        return data

    def make_order(self):
        order, _ = create_order(
            self.user,
            address_id=self.address.pk,
            request_id=uuid4(),
        )
        return order

    def test_anonymous_requests_are_rejected(self):
        order = self.make_order()
        self.client.force_authenticate(user=None)

        requests = (
            ("get", self.list_url, None),
            ("post", self.list_url, self.payload()),
            (
                "get",
                reverse("orders:detail", kwargs={"pk": order.pk}),
                None,
            ),
            (
                "post",
                reverse("orders:cancel", kwargs={"pk": order.pk}),
                {},
            ),
        )

        for method, url, data in requests:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(
                    url,
                    data=data,
                    format="json",
                )
                self.assertEqual(response.status_code, 401)

    def test_create_order_returns_server_calculated_amounts(self):
        response = self.client.post(
            self.list_url,
            self.payload(
                subtotal=1,
                shipping_cost=0,
                total=1,
                status="paid",
                user_id=self.other_user.pk,
            ),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["subtotal"], 200000)
        self.assertEqual(response.data["shipping_cost"], 50000)
        self.assertEqual(response.data["total"], 250000)
        self.assertEqual(response.data["status"], "pending_payment")
        self.assertEqual(len(response.data["items"]), 1)

        order = Order.objects.get(pk=response.data["id"])
        self.assertEqual(order.user_id, self.user.pk)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_duplicate_request_returns_same_order(self):
        payload = self.payload()

        first = self.client.post(
            self.list_url,
            payload,
            format="json",
        )
        second = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Order.objects.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_reused_request_with_changed_data_is_rejected(self):
        payload = self.payload()

        first = self.client.post(
            self.list_url,
            payload,
            format="json",
        )
        payload["customer_note"] = "اطلاعات متفاوت"

        second = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Order.objects.count(), 1)

    def test_invalid_input_is_rejected_without_reserving_stock(self):
        payloads = (
            self.payload(request_id="invalid"),
            self.payload(address_id=0),
            self.payload(customer_note="x" * 1001),
            {"address_id": self.address.pk},
        )

        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    self.list_url,
                    payload,
                    format="json",
                )
                self.assertEqual(response.status_code, 400)

        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_incomplete_profile_cannot_checkout(self):
        self.user.first_name = ""
        self.user.save(update_fields=["first_name"])

        response = self.client.post(
            self.list_url,
            self.payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Order.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_another_users_address_returns_404(self):
        other_address = Address.objects.create(
            user=self.other_user,
            recipient_name="علی رضایی",
            recipient_phone=self.other_user.phone,
            province="تهران",
            city="تهران",
            street_address="خیابان نمونه",
            building_number="1",
            postal_code="1234567890",
        )

        response = self.client.post(
            self.list_url,
            self.payload(address_id=other_address.pk),
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())

    def test_list_only_contains_current_users_orders(self):
        order = self.make_order()

        own_response = self.client.get(self.list_url)

        self.assertEqual(own_response.status_code, 200)
        self.assertEqual(own_response.data["count"], 1)
        self.assertEqual(
            str(own_response.data["results"][0]["id"]),
            str(order.pk),
        )

        self.client.force_authenticate(user=self.other_user)
        other_response = self.client.get(self.list_url)

        self.assertEqual(other_response.status_code, 200)
        self.assertEqual(other_response.data["count"], 0)
        self.assertEqual(other_response.data["results"], [])

    def test_owner_can_read_detail(self):
        order = self.make_order()

        response = self.client.get(
            reverse("orders:detail", kwargs={"pk": order.pk}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data["id"]), str(order.pk))
        self.assertEqual(response.data["city"], "محمدیه")
        self.assertEqual(response.data["items"][0]["quantity"], 2)

    def test_other_user_cannot_read_or_cancel_order(self):
        order = self.make_order()
        self.client.force_authenticate(user=self.other_user)

        detail = self.client.get(
            reverse("orders:detail", kwargs={"pk": order.pk}),
        )
        cancellation = self.client.post(
            reverse("orders:cancel", kwargs={"pk": order.pk}),
            {},
            format="json",
        )

        self.assertEqual(detail.status_code, 404)
        self.assertEqual(cancellation.status_code, 404)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_owner_can_cancel_without_double_stock_release(self):
        order = self.make_order()
        url = reverse("orders:cancel", kwargs={"pk": order.pk})

        first = self.client.post(url, {}, format="json")
        second = self.client.post(url, {}, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["status"], "cancelled")

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        
    def test_expected_total_is_required(self):
        payload = self.payload()
        payload.pop("expected_total")

        response = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_shipping_change_requires_new_confirmation(self):
        payload = self.payload()

        StoreSettings.objects.filter(pk=1).update(
            shipping_cost=70000,
        )

        rejected = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

        # The customer confirms the newly calculated total.
        payload["expected_total"] = 270000

        accepted = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(accepted.status_code, 201)
        self.assertEqual(accepted.data["shipping_cost"], 70000)
        self.assertEqual(accepted.data["total"], 270000)
        self.assertEqual(Order.objects.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

        # Later tariff changes must not break an identical retry.
        StoreSettings.objects.filter(pk=1).update(
            shipping_cost=90000,
        )

        replayed = self.client.post(
            self.list_url,
            payload,
            format="json",
        )

        self.assertEqual(replayed.status_code, 200)
        self.assertEqual(replayed.data["id"], accepted.data["id"])
        self.assertEqual(replayed.data["total"], 270000)
        self.assertEqual(Order.objects.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)