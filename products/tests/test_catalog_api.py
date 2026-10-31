from contextlib import contextmanager
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import transaction
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from dashboard.api.v1.catalog import (
    AttributeDefinitionsView,
    CategorySchemaView,
    ProductCatalogView,
    category_document,
)
from products.models import Attribute, Category, CategoryAttribute, Product


@contextmanager
def test_lock():
    with transaction.atomic():
        yield


class CatalogAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.actor = User.objects.create_user(**{User.USERNAME_FIELD: '09123456789'}, is_staff=True, is_superuser=True)
        self.member = User.objects.create_user(**{User.USERNAME_FIELD: '09123456780'}, is_staff=True)
        self.category = Category(name='کفش', slug='shoes')
        Category.objects.bulk_create([self.category])
        self.product = Product.objects.create(name='کفش', slug='shoe', category=self.category, price=100, stock=1, status='draft', is_active=False)
        self.factory = APIRequestFactory()
        for target in ['products.services.attribute_service.category_tree_write_lock', 'products.services.category_service.category_tree_write_lock', 'dashboard.api.v1.catalog.category_tree_write_lock']:
            mock = patch(target, test_lock)
            mock.start()
            self.addCleanup(mock.stop)

    def call(self, view, method='get', body=None, user=None, purpose='management', **kwargs):
        request = getattr(self.factory, method)('/', body, format='json')
        force_authenticate(request, user=user or self.actor, token={'purpose': purpose})
        return view.as_view()(request, **kwargs)

    def test_customer_token_denied(self):
        response = self.call(ProductCatalogView, purpose='customer', pk=self.product.pk)
        self.assertEqual(response.status_code, 403)

    def test_staff_without_permissions_denied(self):
        response = self.call(ProductCatalogView, user=self.member, pk=self.product.pk)
        self.assertEqual(response.status_code, 403)

    def test_manager_reads_schema_and_creates_typed_definition(self):
        response = self.call(AttributeDefinitionsView, 'post', {'name': 'وزن', 'value_type': 'number', 'unit': 'گرم', 'choices': []})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['value_type'], 'number')
        attr = Attribute.objects.get(pk=response.data['id'])
        CategoryAttribute.objects.create(category=self.category, attribute=attr)
        response = self.call(ProductCatalogView, pk=self.product.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['schema'][0]['unit'], 'گرم')

    def test_schema_revision_prevents_lost_updates(self):
        doc = category_document(self.category.pk)
        attr = Attribute.objects.create(name='جنس', slug='material')
        body = {'revision': doc['revision'], 'rules': [{'attribute_id': attr.pk, 'required': False, 'sort_order': 0}]}
        response = self.call(CategorySchemaView, 'put', body, pk=self.category.pk)
        self.assertEqual(response.status_code, 200, response.data)
        response = self.call(CategorySchemaView, 'put', {'revision': doc['revision'], 'rules': []}, pk=self.category.pk)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(CategoryAttribute.objects.filter(category=self.category).exists())

    def test_publication_requirements_cannot_be_added_silently(self):
        Product.objects.filter(pk=self.product.pk).update(status='published')
        attr = Attribute.objects.create(name='جنس', slug='material')
        body = {'revision': category_document(self.category.pk)['revision'], 'rules': [{'attribute_id': attr.pk, 'required': True, 'sort_order': 0}]}
        response = self.call(CategorySchemaView, 'put', body, pk=self.category.pk)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(CategoryAttribute.objects.filter(category=self.category).exists())

    def test_generic_variant_api_and_duplicate_combination(self):
        body = {'revision': 1, 'action': 'axes', 'data': [{'key': 'size', 'label': 'سایز', 'values': ['40', '41'], 'required': True}]}
        response = self.call(ProductCatalogView, 'post', body, pk=self.product.pk)
        self.assertEqual(response.status_code, 200, response.data)
        body = {'revision': response.data['revision'], 'action': 'variant', 'data': {'sku': 'SH-40', 'options': {'size': '40'}, 'price': 500, 'stock': 2, 'is_active': True}}
        response = self.call(ProductCatalogView, 'post', body, pk=self.product.pk)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['variants'][0]['label'], 'سایز: 40')
        body['revision'] = response.data['revision']
        body['data']['sku'] = 'SH-40-DUPLICATE'
        response = self.call(ProductCatalogView, 'post', body, pk=self.product.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.product.variants.count(), 1)

    def test_variant_of_another_product_is_not_editable(self):
        body = {'revision': 1, 'action': 'axes', 'data': [{'key': 'size', 'label': 'سایز', 'values': ['40'], 'required': True}]}
        response = self.call(ProductCatalogView, 'post', body, pk=self.product.pk)
        body = {'revision': response.data['revision'], 'action': 'variant', 'data': {'id': 999999, 'sku': 'X', 'options': {'size': '40'}, 'price': 100, 'stock': 1, 'expected_stock': 1, 'is_active': True}}
        response = self.call(ProductCatalogView, 'post', body, pk=self.product.pk)
        self.assertEqual(response.status_code, 404)

    def test_definition_update_rejects_invalid_existing_values(self):
        from dashboard.api.v1.catalog import definition
        from products.models import ProductAttributeValue
        attr = Attribute.objects.create(name='جنس', slug='material')
        CategoryAttribute.objects.create(category=self.category, attribute=attr)
        ProductAttributeValue.objects.create(product=self.product, attribute=attr, value='پنبه')
        body = {'name': 'جنس', 'value_type': 'number', 'unit': '', 'choices': [], 'revision': definition(attr)['revision']}
        response = self.call(AttributeDefinitionsView, 'put', body, pk=attr.pk)
        self.assertEqual(response.status_code, 400)
        attr.refresh_from_db()
        self.assertEqual(attr.value_type, 'text')

    def test_definition_revision_prevents_overwrite(self):
        from dashboard.api.v1.catalog import definition
        attr = Attribute.objects.create(name='وزن', slug='weight')
        body = {'name': 'وزن', 'value_type': 'number', 'unit': 'گرم', 'choices': [], 'revision': definition(attr)['revision']}
        response = self.call(AttributeDefinitionsView, 'put', body, pk=attr.pk)
        self.assertEqual(response.status_code, 200, response.data)
        response = self.call(AttributeDefinitionsView, 'put', body, pk=attr.pk)
        self.assertEqual(response.status_code, 400)
