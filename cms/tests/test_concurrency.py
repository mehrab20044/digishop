from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from cms.models import Page
from cms.services.page_service import RevisionConflict, save_page
from cms.tests.helpers import content, user


@skipUnless(connection.vendor == "postgresql", "PostgreSQL row locks required")
class PageConcurrencyTests(TransactionTestCase):
    def test_two_editors_cannot_overwrite_same_revision(self):
        actor = user(is_staff=True)
        page = save_page(actor, content())
        barrier = Barrier(2)

        def edit(title):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    saved = save_page(actor, content(title=title, revision=page.revision), page.pk)
                    return ("saved", saved.title)
                except RevisionConflict:
                    return ("conflict", title)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(edit, ["مدیر اول", "مدیر دوم"]))
        self.assertEqual([result[0] for result in results].count("saved"), 1)
        self.assertEqual([result[0] for result in results].count("conflict"), 1)
        self.assertEqual(Page.objects.get(pk=page.pk).revision, 2)
