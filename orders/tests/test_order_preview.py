from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Address
from cart.models import Cart, CartItem
from orders.models import Order, StoreSettings
from products.models import Category, Product

User = get_user_model()


class OrderPreviewTests(TestCase):
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
        self.address = self.make_address(self.user)
        self.other_address = self.make_address(self.other_user)

        StoreSettings.objects.create(shipping_cost=50000)

        category = Category.objects.create(
            name="تست پیش‌نمایش",
            slug="preview-category",
        )
        self.product = Product.objects.create(
            category=category,
            name="محصول پیش‌نمایش",
            slug="preview-product",
            price=100000,
            stock=5,
            is_active=True,
            status=Product.Status.PUBLISHED,
        )
        self.cart = Cart.objects.create(user=self.user)
        self.item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            selection_key=f"p:{self.product.pk}:v:0",
            product_name=self.product.name,
            quantity=2,
            price_seen=100000,
        )
        self.url = reverse("orders:preview")
        self.client.force_authenticate(user=self.user)

    def make_address(self, user):
        return Address.objects.create(
            user=user,
            recipient_name=user.get_full_name(),
            recipient_phone=user.phone,
            province="قزوین",
            city="محمدیه",
            street_address="خیابان آزمایش",
            building_number="12",
            postal_code="1234567890",
            is_default=True,
        )

    def preview(self, **overrides):
        data = {"address_id": self.address.pk}
        data.update(overrides)

        return self.client.post(
            self.url,
            data,
            format="json",
        )

    def assert_checkout_state_unchanged(self):
        self.product.refresh_from_db()
        self.item.refresh_from_db()

        self.assertEqual(self.product.stock, 5)
        self.assertEqual(self.item.quantity, 2)
        self.assertEqual(self.item.price_seen, 100000)
        self.assertEqual(self.cart.items.count(), 1)
        self.assertFalse(Order.objects.exists())

    def test_preview_returns_amounts_and_two_hour_payment_window(self):
        response = self.preview()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["address_id"], self.address.pk)
        self.assertEqual(response.data["address"]["city"], "محمدیه")
        self.assertEqual(response.data["currency"], "IRT")
        self.assertEqual(response.data["subtotal"], 200000)
        self.assertEqual(response.data["shipping_cost"], 50000)
        self.assertEqual(response.data["total"], 250000)
        self.assertEqual(response.data["reservation_minutes"], 120)
        self.assertEqual(response.data["item_count"], 2)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(
            response.data["items"][0]["unit_price"],
            100000,
        )
        self.assert_checkout_state_unchanged()

    def test_repeated_preview_does_not_reserve_stock(self):
        for _ in range(3):
            response = self.preview()
            self.assertEqual(response.status_code, 200)

        self.assert_checkout_state_unchanged()

    def test_client_cannot_override_preview_amounts(self):
        response = self.preview(
            shipping_cost=0,
            subtotal=1,
            total=1,
            reservation_minutes=9999,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["shipping_cost"], 50000)
        self.assertEqual(response.data["subtotal"], 200000)
        self.assertEqual(response.data["total"], 250000)
        self.assertEqual(response.data["reservation_minutes"], 120)
        self.assert_checkout_state_unchanged()

    def test_anonymous_user_is_rejected(self):
        self.client.force_authenticate(user=None)

        response = self.preview()

        self.assertEqual(response.status_code, 401)
        self.assert_checkout_state_unchanged()

    def test_another_users_address_is_rejected(self):
        response = self.preview(address_id=self.other_address.pk)

        self.assertEqual(response.status_code, 404)
        self.assert_checkout_state_unchanged()

    def test_invalid_address_id_is_rejected(self):
        for address_id in (0, -1, "invalid"):
            with self.subTest(address_id=address_id):
                response = self.preview(address_id=address_id)
                self.assertEqual(response.status_code, 400)

        self.assert_checkout_state_unchanged()

    def test_incomplete_profile_is_rejected(self):
        self.user.last_name = ""
        self.user.save(update_fields=["last_name"])

        response = self.preview()

        self.assertEqual(response.status_code, 403)
        self.assert_checkout_state_unchanged()

    def test_empty_cart_is_rejected(self):
        self.cart.items.all().delete()

        response = self.preview()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_changed_price_is_not_silently_accepted(self):
        Product.objects.filter(pk=self.product.pk).update(
            price=120000,
        )

        response = self.preview()

        self.assertEqual(response.status_code, 400)
        self.assert_checkout_state_unchanged()

    def test_insufficient_stock_is_rejected(self):
        Product.objects.filter(pk=self.product.pk).update(stock=1)

        response = self.preview()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.filter(pk=self.item.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    def test_preview_uses_current_shipping_setting(self):
        StoreSettings.objects.filter(pk=1).update(
            shipping_cost=70000,
        )

        response = self.preview()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["shipping_cost"], 70000)
        self.assertEqual(response.data["total"], 270000)
        self.assert_checkout_state_unchanged()