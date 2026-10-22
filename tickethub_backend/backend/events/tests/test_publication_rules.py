"""Pure content tests: runnable with Python unittest, without Django or a database."""
import unittest
from types import SimpleNamespace as NS
from events.publication import content_issues, is_placeholder_category


def category(**kwargs):
    return NS(**dict({'pk': 'c1', 'slug': 'hockey', 'name_ru': 'Хоккей', 'name_en': 'Ice hockey',
                     'is_active': True, 'is_placeholder': False, 'parent_id': None, 'parent': None}, **kwargs))

def event(**kwargs):
    return NS(**dict({'category': category(), 'title_ru': 'Матч', 'title_en': 'Match',
                     'description_ru': 'Матч на ледовой арене.', 'description_en': 'A game at the arena.'}, **kwargs))


class PublicationRulesTests(unittest.TestCase):
    def test_real_category_allowed(self): self.assertEqual(content_issues(event()), {})
    def test_reserved_slug_forbidden(self): self.assertTrue(is_placeholder_category(category(slug='external-review')))
    def test_explicit_placeholder_forbidden(self): self.assertTrue(is_placeholder_category(category(is_placeholder=True)))
    def test_placeholder_russian_name_forbidden(self): self.assertTrue(is_placeholder_category(category(name_ru='Импортировано — проверить категорию')))
    def test_placeholder_english_name_forbidden(self): self.assertTrue(is_placeholder_category(category(name_en='Uncategorized')))
    def test_missing_category_rejected(self): self.assertIn('category', content_issues(event(category=None)))
    def test_inactive_category_rejected(self): self.assertIn('category', content_issues(event(category=category(is_active=False))))
    def test_inactive_parent_rejected(self): self.assertIn('category', content_issues(event(category=category(parent_id='p',parent=category(pk='p',is_active=False)))))
    def test_real_parent_allowed(self): self.assertEqual(content_issues(event(category=category(parent_id='p',parent=category(pk='p')))), {})
    def test_unresolved_name_rejected(self): self.assertIn('title_ru', content_issues(event(title_ru='{name}')))
    def test_unresolved_city_rejected(self): self.assertIn('description_ru', content_issues(event(description_ru='Матч {city-in}')))
    def test_unresolved_phone_rejected(self): self.assertIn('description_ru', content_issues(event(description_ru='Звоните {phone}.')))
    def test_double_brace_rejected(self): self.assertIn('description_en', content_issues(event(description_en='Visit {{city}}.')))
    def test_source_sales_pitch_rejected(self): self.assertIn('description_ru', content_issues(event(description_ru='Купить билеты можно через Portalbilet.')))
    def test_plain_source_credit_is_not_automatically_rewritten(self): self.assertEqual(content_issues(event(description_ru='Источник: Portalbilet.')), {})
    def test_does_not_mutate_text_or_category(self):
        e=event(title_ru='{name}')
        old=e.category
        content_issues(e)
        self.assertEqual(e.title_ru, '{name}'); self.assertIs(e.category, old)
