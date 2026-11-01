import unittest

from seo.services.robots_engine import evaluate, render_document
from seo.services.robots_text import TextPolicyError, parse_text


class RobotsTextTests(unittest.TestCase):
    def parse(self, text, previous=None):
        return parse_text(text, previous)[0]

    def test_multiple_agents_and_merged_groups(self):
        doc = self.parse('User-agent: Googlebot\nUser-agent: Bingbot\nDisallow: /private/\nUser-agent: Googlebot\nAllow: /private/public$')
        self.assertEqual(len(doc['groups']), 2)
        self.assertTrue(evaluate(doc, '/private/public', 'Googlebot')['allowed'])
        self.assertFalse(evaluate(doc, '/private/public', 'Bingbot')['allowed'])

    def test_pattern_keeps_bare_prefix(self):
        doc = self.parse('User-agent: *\nDisallow: /cart')
        self.assertFalse(evaluate(doc, '/cartoon', 'Googlebot')['allowed'])
        self.assertIn('Disallow: /cart\n', render_document(doc))

    def test_roundtrip_semantics(self):
        doc = self.parse('User-agent: *\nAllow: /\nDisallow: /*?sort=*\nSitemap: https://shop.example/sitemap.xml')
        imported = self.parse(render_document(doc))
        self.assertEqual(render_document(doc), render_document(imported))

    def test_comments_and_case(self):
        doc = self.parse('\ufeff# test\nUSER-AGENT: *\nDisallow: /private/ # note\n')
        self.assertFalse(evaluate(doc, '/private/one', 'Googlebot')['allowed'])

    def test_empty_rule_does_not_block_site(self):
        doc, warnings = parse_text('User-agent: *\nDisallow:')
        self.assertTrue(evaluate(doc, '/', 'Googlebot')['allowed'])
        self.assertEqual(len(warnings), 1)

    def test_bad_directive_reports_exact_line(self):
        with self.assertRaises(TextPolicyError) as error:
            self.parse('User-agent: *\nAllow: /\nNoindex: /secret')
        self.assertEqual(error.exception.line, 3)

    def test_rule_before_agent(self):
        with self.assertRaises(TextPolicyError): self.parse('Disallow: /private')

    def test_invalid_path_line(self):
        with self.assertRaises(TextPolicyError) as error:
            self.parse('User-agent: *\nDisallow: https://evil.example/')
        self.assertEqual(error.exception.line, 2)

    def test_disabled_rules_groups_and_maps_retained(self):
        doc = self.parse('User-agent: *\nDisallow: /off/\nUser-agent: Otherbot\nDisallow: /other/\nSitemap: https://shop.example/sitemap.xml')
        doc['groups'][0]['rules'][0]['enabled'] = False
        doc['groups'][1]['enabled'] = False
        doc['sitemaps'][0]['enabled'] = False
        result = self.parse('User-agent: *\nAllow: /', doc)
        self.assertFalse(result['groups'][0]['rules'][-1]['enabled'])
        self.assertFalse(result['groups'][1]['enabled'])
        self.assertFalse(result['sitemaps'][0]['enabled'])

    def test_sitemap_bad_scheme(self):
        with self.assertRaises(TextPolicyError): self.parse('User-agent: *\nSitemap: javascript:alert(1)')

    def test_limits(self):
        with self.assertRaises(TextPolicyError): self.parse('User-agent: *\n' + 'Disallow: /x\n'*4001)
        with self.assertRaises(TextPolicyError): self.parse('x'*480001)

    def test_all_comments_rejected(self):
        with self.assertRaises(TextPolicyError): self.parse('# empty')
