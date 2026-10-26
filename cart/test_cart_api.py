import hashlib
import uuid

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from products.models import Category, Product, ProductVariant
from cart.models import Cart, CartItem, CartOperation

BASE = '/api/v1/cart/'


class ShoppingCartTests(TestCase):
    def setUp(self):
        cache.clear()
        self.category = Category.objects.create(name='Cart test category', slug='cart-test')
        self.product = Product.objects.create(category=self.category, name='Phone', slug='cart-test-phone', price=1000, stock=10)
        self.variant = ProductVariant.objects.create(product=self.product, sku='CART-TEST-1', color='Green', price=1500, stock=5)
        self.client = self.guest('a')
        self.other = self.guest('b')

    def guest(self, letter):
        client = APIClient()
        client.credentials(HTTP_X_CART_TOKEN=letter * 64)
        return client

    def user(self, suffix='1'):
        model = get_user_model()
        identifier = '0912000000' + suffix if model.USERNAME_FIELD == 'phone' else 'cart-user-' + suffix
        return model.objects.create_user(**{model.USERNAME_FIELD: identifier}, password='cart-tests-only')

    def add(self, client=None, **overrides):
        data = {'product_id': self.product.pk, 'variant_id': self.variant.pk, 'quantity': 1, 'request_id': str(uuid.uuid4())}
        data.update(overrides)
        return (client or self.client).post(BASE + 'items/', data, format='json')

    def test_guest_read_is_empty_without_database_write(self):
        response = self.client.get(BASE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['items'], [])
        self.assertEqual(Cart.objects.count(), 0)
        self.assertIn('no-store', response['Cache-Control'])

    def test_read_without_token_is_empty(self):
        response = APIClient().get(BASE)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['item_count'], 0)

    def test_guest_can_add_variant_with_server_price(self):
        response = self.add(quantity=2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['subtotal'], 3000)
        self.assertEqual(response.data['item_count'], 2)
        self.assertEqual(response.data['items'][0]['unit_price'], 1500)
        self.assertTrue(response.data['can_checkout'])
        self.assertEqual(Cart.objects.get().guest_digest, hashlib.sha256(('a' * 64).encode()).hexdigest())

    def test_simple_product_can_be_added_without_variant(self):
        simple = Product.objects.create(category=self.category, name='Cable', slug='cart-test-cable', price=90, stock=7)
        response = self.add(product_id=simple.pk, variant_id=None, quantity=3)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['subtotal'], 270)

    def test_variant_is_required_when_product_has_variants(self):
        self.assertEqual(self.add(variant_id=None).status_code, 400)

    def test_variant_must_belong_to_product(self):
        simple = Product.objects.create(category=self.category, name='Other', slug='cart-test-other', price=100, stock=5)
        self.assertEqual(self.add(product_id=simple.pk).status_code, 404)

    def test_draft_and_inactive_products_are_not_addable(self):
        self.product.status = 'draft'
        self.product.save()
        self.assertEqual(self.add().status_code, 404)
        self.product.status = 'published'
        self.product.is_active = False
        self.product.save()
        self.assertEqual(self.add().status_code, 404)

    def test_inactive_variant_is_not_addable(self):
        self.variant.is_active = False
        self.variant.save()
        self.assertEqual(self.add().status_code, 404)

    def test_zero_price_and_zero_stock_are_rejected(self):
        for field in ['price', 'stock']:
            with self.subTest(field=field):
                ProductVariant.objects.filter(pk=self.variant.pk).update(**{field: 0})
                self.assertEqual(self.add().status_code, 400)
                ProductVariant.objects.filter(pk=self.variant.pk).update(price=1500, stock=5)

    def test_invalid_quantities_are_rejected(self):
        for quantity in [0, -1, 100, 1.5, True, '2', None]:
            with self.subTest(quantity=quantity):
                self.assertEqual(self.add(quantity=quantity).status_code, 400)
        self.assertFalse(CartItem.objects.exists())

    def test_client_cannot_supply_price_or_user(self):
        for key in ['price', 'unit_price', 'user_id', 'cart_id']:
            with self.subTest(key=key):
                self.assertEqual(self.add(**{key: 1}).status_code, 400)

    def test_repeated_add_accumulates_and_checks_total_stock(self):
        self.assertEqual(self.add(quantity=3).status_code, 200)
        self.assertEqual(self.add(quantity=3).status_code, 400)
        self.assertEqual(CartItem.objects.get().quantity, 3)
        self.assertEqual(self.add(quantity=2).status_code, 200)
        self.assertEqual(CartItem.objects.get().quantity, 5)

    def test_retried_request_does_not_add_twice(self):
        request_id = str(uuid.uuid4())
        self.add(request_id=request_id, quantity=2)
        response = self.add(request_id=request_id, quantity=2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['item_count'], 2)
        self.assertEqual(CartOperation.objects.count(), 1)

    def test_reused_request_id_with_different_data_is_rejected(self):
        request_id = str(uuid.uuid4())
        self.add(request_id=request_id)
        self.assertEqual(self.add(request_id=request_id, quantity=2).status_code, 400)
        self.assertEqual(CartItem.objects.get().quantity, 1)

    def test_guest_savings_survive_a_new_client_with_same_token(self):
        self.add()
        self.assertEqual(self.guest('a').get(BASE).data['item_count'], 1)
        self.assertEqual(self.other.get(BASE).data['item_count'], 0)

    def test_other_guest_cannot_update_or_delete_item(self):
        item_id = self.add().data['items'][0]['id']
        self.assertEqual(self.other.patch(f'{BASE}items/{item_id}/', {'quantity': 2}, format='json').status_code, 404)
        self.assertEqual(self.other.delete(f'{BASE}items/{item_id}/').status_code, 404)
        self.assertEqual(CartItem.objects.get().quantity, 1)

    def test_update_and_remove(self):
        item_id = self.add().data['items'][0]['id']
        response = self.client.patch(f'{BASE}items/{item_id}/', {'quantity': 4}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['subtotal'], 6000)
        self.assertEqual(self.client.delete(f'{BASE}items/{item_id}/').data['items'], [])

    def test_stock_change_preserves_item_and_warns(self):
        self.add(quantity=4)
        ProductVariant.objects.filter(pk=self.variant.pk).update(stock=2)
        response = self.client.get(BASE)
        self.assertEqual(response.data['items'][0]['quantity'], 4)
        self.assertTrue(response.data['has_issues'])
        self.assertFalse(response.data['can_checkout'])
        item_id = response.data['items'][0]['id']
        self.assertEqual(self.client.patch(f'{BASE}items/{item_id}/', {'quantity': 3}, format='json').status_code, 400)
        self.assertTrue(self.client.patch(f'{BASE}items/{item_id}/', {'quantity': 2}, format='json').data['can_checkout'])

    def test_price_change_uses_new_price_until_explicit_confirmation(self):
        item_id = self.add().data['items'][0]['id']
        ProductVariant.objects.filter(pk=self.variant.pk).update(price=1800)
        response = self.client.get(BASE)
        self.assertEqual(response.data['subtotal'], 1800)
        self.assertTrue(response.data['items'][0]['price_changed'])
        self.assertFalse(response.data['can_checkout'])
        response = self.client.patch(f'{BASE}items/{item_id}/', {'quantity': 1}, format='json')
        self.assertTrue(response.data['can_checkout'])

    def test_deleted_variant_does_not_fall_back_to_product_price(self):
        item_id = self.add().data['items'][0]['id']
        self.variant.delete()
        response = self.client.get(BASE)
        self.assertEqual(response.data['items'][0]['id'], item_id)
        self.assertIsNone(response.data['items'][0]['unit_price'])
        self.assertFalse(response.data['can_checkout'])
        self.assertEqual(self.client.patch(f'{BASE}items/{item_id}/', {'quantity': 1}, format='json').status_code, 400)

    def test_deleted_product_remains_visible_as_unavailable(self):
        self.add()
        self.product.delete()
        response = self.client.get(BASE)
        self.assertEqual(response.data['items'][0]['name'], 'Phone')
        self.assertIsNone(response.data['items'][0]['product_id'])
        self.assertFalse(response.data['items'][0]['available'])

    def test_unpublished_product_does_not_expose_new_draft_price_or_name(self):
        self.add()
        Product.objects.filter(pk=self.product.pk).update(status='draft', name='Secret draft name', price=99999)
        response = self.client.get(BASE)
        self.assertEqual(response.data['items'][0]['name'], 'Phone')
        self.assertIsNone(response.data['items'][0]['unit_price'])

    def test_guest_merge_requires_authentication(self):
        self.assertIn(self.client.post(BASE + 'merge/', {}, format='json').status_code, [401, 403])

    def test_merge_combines_quantities_and_is_idempotent(self):
        self.add(quantity=2)
        user = self.user()
        owner = APIClient()
        owner.force_authenticate(user)
        self.add(owner, quantity=1)
        owner.credentials(HTTP_X_CART_TOKEN='a' * 64)
        merged = owner.post(BASE + 'merge/', {}, format='json')
        self.assertEqual(merged.status_code, 200)
        self.assertEqual(merged.data['item_count'], 3)
        self.assertEqual(owner.post(BASE + 'merge/', {}, format='json').data['item_count'], 3)
        self.assertEqual(self.client.get(BASE).data['items'], [])
        self.assertEqual(Cart.objects.count(), 1)

    def test_merge_preserves_stock_and_price_warnings(self):
        self.add(quantity=4)
        ProductVariant.objects.filter(pk=self.variant.pk).update(stock=1, price=2000)
        self.client.force_authenticate(self.user())
        response = self.client.post(BASE + 'merge/', {}, format='json')
        self.assertEqual(response.data['items'][0]['quantity'], 4)
        self.assertTrue(response.data['has_issues'])

    def test_user_cannot_read_or_mutate_another_user_cart(self):
        self.client.force_authenticate(self.user('1'))
        item_id = self.add().data['items'][0]['id']
        self.other.force_authenticate(self.user('2'))
        self.assertEqual(self.other.get(BASE).data['items'], [])
        self.assertEqual(self.other.delete(f'{BASE}items/{item_id}/').status_code, 404)

    def test_idempotency_key_survives_merge(self):
        request_id = str(uuid.uuid4())
        self.add(request_id=request_id)
        self.client.force_authenticate(self.user())
        self.client.post(BASE + 'merge/', {}, format='json')
        response = self.add(request_id=request_id)
        self.assertEqual(response.data['item_count'], 1)

    def test_malformed_guest_token_does_not_create_cart(self):
        self.client.credentials(HTTP_X_CART_TOKEN='guessed')
        self.assertEqual(self.add().status_code, 400)
        self.assertEqual(Cart.objects.count(), 0)

    def test_add_does_not_reserve_inventory(self):
        self.add(quantity=2)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 5)

    def test_no_token_cannot_create_guest_cart(self):
        self.assertEqual(self.add(APIClient()).status_code, 400)
        self.assertFalse(Cart.objects.exists())

    def test_merge_quantity_limit_has_explicit_notice(self):
        ProductVariant.objects.filter(pk=self.variant.pk).update(stock=250)
        self.add(quantity=60)
        owner = APIClient()
        owner.force_authenticate(self.user())
        self.add(owner, quantity=60)
        owner.credentials(HTTP_X_CART_TOKEN='a' * 64)
        response = owner.post(BASE + 'merge/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['item_count'], 99)
        self.assertTrue(response.data['notices'])

    def test_variant_reassigned_to_other_product_is_not_usable(self):
        self.add()
        other = Product.objects.create(category=self.category, name='Other', slug='moved-variant', price=100, stock=4)
        ProductVariant.objects.filter(pk=self.variant.pk).update(product=other)
        item = self.client.get(BASE).data['items'][0]
        self.assertFalse(item['available'])
        self.assertIsNone(item['unit_price'])

    def test_changed_variant_description_requires_confirmation(self):
        item_id = self.add().data['items'][0]['id']
        ProductVariant.objects.filter(pk=self.variant.pk).update(color='Blue')
        response = self.client.get(BASE)
        self.assertTrue(response.data['items'][0]['selection_changed'])
        self.assertFalse(response.data['can_checkout'])
        response = self.client.patch(f'{BASE}items/{item_id}/', {'quantity': 1}, format='json')
        self.assertFalse(response.data['items'][0]['selection_changed'])
        self.assertTrue(response.data['can_checkout'])
