import copy
import unittest

from seo.services import robots_engine as e

def rule(path,action='disallow',scope='pattern',id='r',enabled=True):return dict(id=id,path=path,action=action,scope=scope,enabled=enabled)
def group(agent='*',rules=None,id='all',enabled=True):return dict(id=id,agent=agent,rules=rules or [],enabled=enabled)
def doc(groups=None,sitemaps=None):return dict(version=1,groups=groups or [group()],sitemaps=sitemaps or [])
class EngineTests(unittest.TestCase):
 def check(self,document,path,agent='Googlebot'):return e.evaluate(e.validate_document(document),path,agent)
 def test_root_block(self):self.assertFalse(self.check(doc([group(rules=[rule('/')])]),'/products')['allowed'])
 def test_exact_does_not_match_queries_or_descendants(self):
  d=doc([group(rules=[rule('/products/12',scope='exact')])]);self.assertFalse(self.check(d,'/products/12')['allowed'])
  for path in ['/products/123','/products/12/x','/products/12?x=1']:self.assertTrue(self.check(d,path)['allowed'])
 def test_prefix_does_not_match_sibling(self):
  d=doc([group(rules=[rule('/cart',scope='prefix')])]);self.assertFalse(self.check(d,'/cart/line')['allowed']);self.assertTrue(self.check(d,'/cartoon/')['allowed'])
 def test_specific_group_does_not_inherit_wildcard(self):
  d=doc([group(rules=[rule('/')]),group('Googlebot',[],id='google')]);self.assertTrue(self.check(d,'/x')['allowed']);self.assertFalse(self.check(d,'/x','Bingbot')['allowed'])
 def test_longest_agent_selected(self):
  d=doc([group('Googlebot',[rule('/')],id='g'),group('Googlebot-News',[],id='n')]);self.assertTrue(self.check(d,'/x','Googlebot-News')['allowed'])
 def test_agent_case_insensitive_path_case_sensitive(self):
  d=doc([group('Googlebot',[rule('/A')])]);self.assertFalse(self.check(d,'/A','googlebot')['allowed']);self.assertTrue(self.check(d,'/a','GOOGLEBOT')['allowed'])
 def test_longest_rule_wins(self):
  d=doc([group(rules=[rule('/',id='a'),rule('/products/','allow',id='b')])]);self.assertTrue(self.check(d,'/products/12')['allowed'])
 def test_allow_wins_tie(self):
  d=doc([group(rules=[rule('/x',id='a'),rule('/x','allow',id='b')])]);self.assertTrue(self.check(d,'/x')['allowed'])
 def test_wildcard_and_dollar(self):
  d=doc([group(rules=[rule('/*.pdf$')])]);self.assertFalse(self.check(d,'/files/a.pdf')['allowed']);self.assertTrue(self.check(d,'/a.pdf?x=1')['allowed'])
 def test_multiple_wildcards(self):
  self.assertTrue(e.pattern_matches('/a*b*c$','/axbyc'));self.assertFalse(e.pattern_matches('/a*b*c$','/axbycd'))
 def test_root_anchor_more_specific(self):
  d=doc([group(rules=[rule('/',id='a'),rule('/$','allow',id='b')])]);self.assertTrue(self.check(d,'/')['allowed']);self.assertFalse(self.check(d,'/page')['allowed'])
 def test_unicode_and_percent_equivalent(self):
  d=doc([group(rules=[rule('/رم',scope='exact')])]);self.assertFalse(self.check(d,'/%D8%B1%D9%85')['allowed'])
 def test_percent_hex_case_equivalent(self):
  d=doc([group(rules=[rule('/x%2Fz')])]);self.assertFalse(self.check(d,'/x%2fz')['allowed']);self.assertTrue(self.check(d,'/x/z')['allowed'])
 def test_unreserved_percent_decoded(self):self.assertEqual(e.normalized_path('/%61'),'/a')
 def test_disabled_rule_and_group(self):
  d=doc([group(rules=[rule('/',enabled=False)]),group('Googlebot',[rule('/')],id='g',enabled=False)]);self.assertTrue(self.check(d,'/x')['allowed'])
 def test_empty_group_has_explicit_allow(self):self.assertEqual(e.render_document(doc()),'User-agent: *\nAllow: /\n')
 def test_groups_separated(self):
  d=doc([group(),group('Googlebot',id='g')]);self.assertIn('Allow: /\n\nUser-agent: Googlebot',e.render_document(d))
 def test_sitemap_full_absolute_and_disabled(self):
  d=doc(sitemaps=[dict(id='s',url='https://shop.example/sitemap.xml',enabled=True),dict(id='off',url='https://shop.example/other.xml',enabled=False)]);text=e.render_document(e.validate_document(d));self.assertIn('Sitemap: https://shop.example/sitemap.xml',text);self.assertNotIn('other.xml',text)
 def test_line_injection_rejected(self):
  for bad in ['*\nDisallow: /','Googlebot: bad']:
   with self.assertRaises(e.PolicyError):e.validate_document(doc([group(bad)]))
  with self.assertRaises(e.PolicyError):e.validate_document(doc([group(rules=[rule('/x\nAllow: /')])]))
 def test_invalid_scopes_and_percent(self):
  for item in [rule('/x*',scope='exact'),rule('/x$y'),rule('/bad%xx')]:
   with self.assertRaises(e.PolicyError):e.validate_document(doc([group(rules=[item])]))
 def test_duplicate_agents_case_insensitive(self):
  with self.assertRaises(e.PolicyError):e.validate_document(doc([group('Googlebot'),group('googlebot',id='b')]))
 def test_duplicate_rule_ids(self):
  with self.assertRaises(e.PolicyError):e.validate_document(doc([group(rules=[rule('/a'),rule('/b')])]))
 def test_bad_sitemap_credentials_fragment(self):
  for url in ['javascript:alert(1)','https://a:b@shop.example/sitemap.xml','https://shop.example/map.xml#x','https://shop.example\nAllow: /']:
   with self.assertRaises(e.PolicyError):e.validate_document(doc(sitemaps=[dict(id='s',url=url,enabled=True)]))
 def test_input_not_mutated(self):
  d=doc([group(rules=[rule('/cart',scope='prefix')])]);old=copy.deepcopy(d);e.validate_document(d);self.assertEqual(d,old)
 def test_foreign_url_not_fetched_or_accepted(self):
  with self.assertRaises(e.PolicyError):e.evaluate(doc(),'https://evil.example/x')
 def test_rules_order_does_not_override_specificity(self):
  a=rule('/products/','allow',id='a');b=rule('/',id='b');d=doc([group(rules=[a,b])]);self.assertTrue(self.check(d,'/products/a')['allowed'])
if __name__=='__main__':unittest.main()
