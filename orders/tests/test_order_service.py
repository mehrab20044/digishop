from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.test import TestCase
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
from products.models import Category, Product, ProductVariant

User = get_user_model()


class OrderServiceTests(TestCase):
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
        StoreSettings.objects.create(
            shipping_cost=50000,
        )
        self.category = Category.objects.create(
            name="آزمایشی",
            slug="test-category",
        )
        self.product = Product.objects.create(
            category=self.category,
            name="محصول آزمایشی",
            slug="test-product",
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
            price_seen=self.product.price,
        )

    def checkout(self, **overrides):
        data = {
            "address_id": self.address.pk,
            "request_id": uuid4(),
        }
        data.update(overrides)

        return create_order(self.user, **data)

    def test_checkout_reserves_stock_and_clears_cart(self):
        started_at = timezone.now()

        order, created = self.checkout()

        self.assertTrue(created)
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)
        self.assertEqual(order.subtotal, 200000)
        self.assertEqual(order.shipping_cost, 50000)
        self.assertEqual(order.total, 250000)
        self.assertEqual(order.currency, "IRT")
        self.assertGreaterEqual(
            order.expires_at,
            started_at + timedelta(hours=2),
        )
        self.assertLessEqual(
            order.expires_at,
            timezone.now() + timedelta(hours=2),
        )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertFalse(self.cart.items.exists())

        line = order.items.get()
        self.assertEqual(line.quantity, 2)
        self.assertEqual(line.unit_price, 100000)
        self.assertEqual(line.line_total, 200000)

    def test_same_request_returns_existing_order(self):
        request_id = uuid4()

        first, first_created = self.checkout(request_id=request_id)
        second, second_created = self.checkout(request_id=request_id)

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Order.objects.count(), 1)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_same_request_with_different_data_is_rejected(self):
        request_id = uuid4()
        self.checkout(request_id=request_id)

        with self.assertRaises(ValidationError):
            self.checkout(
                request_id=request_id,
                customer_note="اطلاعات متفاوت",
            )

        self.assertEqual(Order.objects.count(), 1)

    def test_another_users_address_is_rejected(self):
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

        with self.assertRaises(Http404):
            self.checkout(address_id=other_address.pk)

        self.assertFalse(Order.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)
        self.assertTrue(self.cart.items.exists())

    def test_changed_price_requires_cart_confirmation(self):
        Product.objects.filter(pk=self.product.pk).update(
            price=120000,
        )

        with self.assertRaises(ValidationError):
            self.checkout()

        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_insufficient_stock_does_not_create_order(self):
        Product.objects.filter(pk=self.product.pk).update(stock=1)

        with self.assertRaises(ValidationError):
            self.checkout()

        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    def test_order_keeps_original_address_price_and_shipping(self):
        order, _ = self.checkout()

        Address.objects.filter(pk=self.address.pk).update(
            city="تهران",
            street_address="آدرس جدید",
        )
        Product.objects.filter(pk=self.product.pk).update(
            name="نام جدید",
            price=900000,
        )
        StoreSettings.objects.filter(pk=1).update(
            shipping_cost=90000,
        )

        order.refresh_from_db()
        line = order.items.get()

        self.assertEqual(order.city, "محمدیه")
        self.assertEqual(order.street_address, "خیابان آزمایش")
        self.assertEqual(order.shipping_cost, 50000)
        self.assertEqual(line.product_name, "محصول آزمایشی")
        self.assertEqual(line.unit_price, 100000)
        self.assertEqual(order.total, 250000)

    def test_cancel_releases_stock_only_once(self):
        order, _ = self.checkout()

        first = cancel_order(self.user, order_id=order.pk)
        second = cancel_order(self.user, order_id=order.pk)

        self.assertEqual(first.status, Order.Status.CANCELLED)
        self.assertEqual(second.status, Order.Status.CANCELLED)
        self.assertIsNotNone(second.cancelled_at)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_cannot_cancel_another_users_order(self):
        order, _ = self.checkout()

        with self.assertRaises(Http404):
            cancel_order(self.other_user, order_id=order.pk)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_expire_releases_stock_only_once(self):
        order, _ = self.checkout()
        now = timezone.now()

        # Keep the database constraint expires_at > created_at valid.
        Order.objects.filter(pk=order.pk).update(
            created_at=now - timedelta(hours=3),
            expires_at=now - timedelta(hours=1),
        )

        self.assertTrue(expire_order(order_id=order.pk))
        self.assertFalse(expire_order(order_id=order.pk))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.EXPIRED)
        self.assertIsNotNone(order.expired_at)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)

    def test_order_does_not_expire_before_deadline(self):
        order, _ = self.checkout()

        self.assertFalse(expire_order(order_id=order.pk))

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING_PAYMENT)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_paid_order_does_not_expire_or_release_stock(self):
        order, _ = self.checkout()
        now = timezone.now()

        # Set up a paid state; this does not implement payment verification.
        Order.objects.filter(pk=order.pk).update(
            status=Order.Status.PAID,
            paid_at=now,
            created_at=now - timedelta(hours=3),
            expires_at=now - timedelta(hours=1),
        )

        self.assertFalse(expire_order(order_id=order.pk))

        with self.assertRaises(ValidationError):
            cancel_order(self.user, order_id=order.pk)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    def test_variant_stock_is_reserved_and_released(self):
        self.cart.items.all().delete()

        variant = ProductVariant.objects.create(
            product=self.product,
            sku="TEST-BLACK-128",
            color="مشکی",
            storage="128",
            price=150000,
            stock=4,
        )
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            variant=variant,
            selection_key=f"p:{self.product.pk}:v:{variant.pk}",
            product_name=self.product.name,
            variant_name="مشکی / 128",
            had_variant=True,
            quantity=2,
            price_seen=150000,
        )

        order, _ = self.checkout()

        variant.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(variant.stock, 2)
        self.assertEqual(self.product.stock, 5)
        self.assertEqual(order.subtotal, 300000)
        self.assertEqual(order.items.get().sku, "TEST-BLACK-128")

        cancel_order(self.user, order_id=order.pk)

        variant.refresh_from_db()
        self.assertEqual(variant.stock, 4)

    def test_missing_shipping_settings_rolls_back_checkout(self):
        StoreSettings.objects.all().delete()

        with self.assertRaises(ImproperlyConfigured):
            self.checkout()

        self.assertFalse(Order.objects.exists())
        self.assertTrue(self.cart.items.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)