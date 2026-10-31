from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from cms.api.v1.views import PageDetailView, PageListCreateView, PagePublishView
from cms.tests.helpers import content, user


class CMSAPIPermissionTests(TestCase):
    """Exercise CMS validation and model permissions; existing management authentication is isolated here."""
    def setUp(self):
        self.factory = APIRequestFactory()
        self.actor = user(is_staff=True, is_superuser=True)
        self.member = user("09120000002", is_staff=True)
        self.auth_boundary = patch("cms.api.v1.views.OwnerAPIView.initial", return_value=None)
        self.auth_boundary.start()
        self.addCleanup(self.auth_boundary.stop)

    def request(self, view, method="post", data=None, actor=None, **kwargs):
        request = getattr(self.factory, method)("/", data or {}, format="json")
        force_authenticate(request, user=actor or self.actor)
        return view.as_view()(request, **kwargs)

    def test_create_requires_add_and_view(self):
        response = self.request(PageListCreateView, data=content(), actor=self.member)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.request(PageListCreateView, data=content()).status_code, 201)

    def test_update_conflict_is_409(self):
        page = self.request(PageListCreateView, data=content()).data
        response = self.request(PageDetailView, "patch", content(revision=page["revision"]), pk=page["id"])
        self.assertEqual(response.status_code, 200)
        response = self.request(PageDetailView, "patch", content(revision=page["revision"]), pk=page["id"])
        self.assertEqual(response.status_code, 409)

    def test_unauthorized_publish_is_rejected(self):
        from django.contrib.auth.models import Permission
        self.member.user_permissions.add(Permission.objects.get(content_type__app_label="cms", codename="view_page"))
        page = self.request(PageListCreateView, data=content()).data
        response = self.request(PagePublishView, data={"revision": page["revision"]}, actor=self.member, pk=page["id"])
        self.assertEqual(response.status_code, 403)

    def test_publish_and_list(self):
        page = self.request(PageListCreateView, data=content()).data
        self.assertEqual(self.request(PagePublishView, data={"revision": page["revision"]}, pk=page["id"]).status_code, 200)
        response = self.request(PageListCreateView, "get")
        self.assertEqual(response.data["count"], 1)

    def test_unknown_write_field_rejected(self):
        self.assertEqual(self.request(PageListCreateView, data=content(is_published=True)).status_code, 400)
