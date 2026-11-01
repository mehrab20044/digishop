from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from cms.tests.helpers import user
from products.models import Category, Product
from seo.models import PageSearchRule
from seo.page_rules_api import PageRulesView
from seo.robots_api import RobotsStudioView
from seo.services.index_manager import bulk_index, list_index_targets
from seo.services.page_rules import RuleConflict
from seo.services.robots_service import current_document


@override_settings(SITE_PUBLIC_URL='https://shop.example')
class IndexManagerTests(TestCase):
    def setUp(self):
        self.actor = user(is_staff=True, is_superuser=True)
        self.category = Category.objects.bulk_create([Category(name='تست', slug='index-test')])[0]
        self.a = Product.objects.create(name='محصول الف', slug='ix-a', category=self.category, price=1000, stock=2, is_active=True, status=Product.Status.PUBLISHED)
        self.b = Product.objects.create(name='محصول ب', slug='ix-b', category=self.category, price=1000, stock=2, is_active=True, status=Product.Status.PUBLISHED)

    def items(self):
        return [{'kind':'product','object_id':obj.pk,'expected_version':0} for obj in (self.a,self.b)]

    def test_bulk_save_and_no_crawl_mutation(self):
        result = bulk_index(actor=self.actor, items=self.items(), indexing='noindex')
        self.assertEqual(result['updated'], 2)
        self.assertEqual(PageSearchRule.objects.filter(indexing='noindex', crawl='inherit').count(), 2)

    def test_conflict_rolls_back_entire_batch(self):
        PageSearchRule.objects.create(kind='product', object_id=self.b.pk, version=1)
        with self.assertRaises(RuleConflict): bulk_index(actor=self.actor, items=self.items(), indexing='noindex')
        self.assertFalse(PageSearchRule.objects.filter(object_id=self.a.pk).exists())
        self.assertEqual(PageSearchRule.objects.get(object_id=self.b.pk).indexing, 'inherit')

    def test_duplicate_rejected(self):
        items=self.items()
        with self.assertRaises(ValidationError): bulk_index(actor=self.actor, items=[items[0],items[0]], indexing='noindex')

    def test_permission(self):
        with self.assertRaises(PermissionDenied): bulk_index(actor=user(number='09120000002'), items=self.items(), indexing='noindex')

    def test_filter_and_inherit_without_rule(self):
        bulk_index(actor=self.actor, items=[self.items()[0]], indexing='noindex')
        rows=list_index_targets(indexing='noindex')['results']
        self.assertEqual([row['object_id'] for row in rows], [self.a.pk])
        rows=list_index_targets(indexing='inherit')['results']
        self.assertEqual([row['object_id'] for row in rows], [self.b.pk])

    def test_category_descendants_and_secondary_membership(self):
        child=Category.objects.bulk_create([Category(name='فرزند', slug='ix-child', parent=self.category)])[0]
        other=Category.objects.bulk_create([Category(name='دیگر', slug='ix-other')])[0]
        self.b.category=other; self.b.save();self.b.categories.add(child)
        result=list_index_targets(category=self.category.pk)
        self.assertEqual(result['count'],2)

    def test_search_id_and_pagination(self):
        result=list_index_targets(search=str(self.a.pk),page_size=20)
        self.assertIn(self.a.pk,[row['object_id'] for row in result['results']])
        self.assertEqual(list_index_targets(page=2)['results'],[])

    def test_mixed_index_values(self):
        items=self.items();items[0]['indexing']='noindex';items[1]['indexing']='index'
        bulk_index(actor=self.actor,items=items,indexing='inherit')
        self.assertEqual(PageSearchRule.objects.get(object_id=self.a.pk).indexing,'noindex')
        self.assertEqual(PageSearchRule.objects.get(object_id=self.b.pk).indexing,'index')

    def call(self, view, data, actor=None):
        request=APIRequestFactory().post('/',data,format='json');force_authenticate(request,user=actor or self.actor, token={"purpose":"management"})
        return view.as_view()(request)

    def test_bulk_endpoint(self):
        response=self.call(PageRulesView,{'action':'bulk_index','items':self.items(),'indexing':'noindex'})
        self.assertEqual(response.status_code,200)

    def test_parse_api_does_not_publish(self):
        before=current_document().published
        response=self.call(RobotsStudioView,{'action':'parse','text':'User-agent: *\nAllow: /'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(current_document().published,before)

    def test_parse_api_reports_line(self):
        response=self.call(RobotsStudioView,{'action':'parse','text':'User-agent: *\nNoindex: /'})
        self.assertEqual(response.status_code,400);self.assertEqual(response.data['line'],2)
