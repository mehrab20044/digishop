from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import TestCase, override_settings
from PIL import Image
from products.models import Category
from rest_framework.test import APIClient


class CategoryShowcaseTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        media = override_settings(MEDIA_ROOT=self.tmp.name)
        media.enable()
        self.addCleanup(media.disable)
        lock = patch(
            "products.services.category_showcase_service.category_tree_write_lock",
            transaction.atomic,
        )
        lock.start()
        self.addCleanup(lock.stop)
        Category.objects.bulk_create(
            [
                Category(
                    name=f"Category {i}",
                    slug=f"showcase-{i}",
                    image=f"categories/{i}.webp",
                )
                for i in range(7)
            ]
        )
        self.rows = list(Category.objects.order_by("pk"))
        self.ids = [c.pk for c in self.rows[:5]]
        self.admin = get_user_model().objects.create_superuser(
            phone="09123456780", password="test"
        )
        self.api = APIClient()
        self.api.force_authenticate(self.admin, token={"purpose": "management"})

    def image(self, name="test.png"):
        output = BytesIO()
        Image.new("RGB", (32, 24), "blue").save(output, "PNG")
        return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")

    def choose(self, ids=None, expected=None):
        return self.api.put(
            "/api/v1/owner/category-showcase/",
            {
                "category_ids": ids if ids is not None else self.ids,
                "expected_ids": expected or [],
            },
            format="json",
        )

    def test_exact_five_are_saved_in_order_and_public_tree_exposes_images(self):
        self.assertEqual(self.choose().status_code, 200)
        self.assertEqual(
            list(
                Category.objects.filter(is_home_featured=True)
                .order_by("home_featured_order")
                .values_list("pk", flat=True)
            ),
            self.ids,
        )
        self.api.force_authenticate(None)
        response = self.api.get("/products/api/v1/categories/tree/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sum(row["is_home_featured"] for row in response.data), 5
        )
        self.assertTrue(response.data[0]["image_url"].startswith("/media/categories/"))

    def test_reorder_and_replace_is_atomic(self):
        self.assertEqual(self.choose().status_code, 200)
        next_ids = [self.rows[5].pk, *reversed(self.ids[1:])]
        response = self.choose(next_ids, self.ids)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["category_ids"], next_ids)
        self.assertFalse(Category.objects.get(pk=self.ids[0]).is_home_featured)

    def test_rejects_invalid_selection_and_keeps_previous(self):
        self.choose()
        for ids in [
            self.ids[:4],
            self.ids + [self.rows[5].pk],
            [self.ids[0]] * 5,
            [True, *self.ids[1:]],
            [999999, *self.ids[1:]],
        ]:
            with self.subTest(ids=ids):
                self.assertEqual(self.choose(ids, self.ids).status_code, 400)
        self.assertEqual(
            list(
                Category.objects.filter(is_home_featured=True)
                .order_by("home_featured_order")
                .values_list("pk", flat=True)
            ),
            self.ids,
        )

    def test_missing_image_rejected(self):
        Category.objects.filter(pk=self.ids[0]).update(image="")
        self.assertEqual(self.choose().status_code, 400)
        self.assertFalse(Category.objects.filter(is_home_featured=True).exists())

    def test_stale_selection_cannot_overwrite(self):
        self.choose()
        self.assertEqual(self.choose(list(reversed(self.ids)), []).status_code, 409)

    def test_nested_category_can_be_featured_and_stays_nested(self):
        Category.objects.filter(pk=self.ids[1]).update(parent_id=self.ids[0])
        self.assertEqual(self.choose().status_code, 200)
        response = self.api.get("/products/api/v1/categories/tree/")
        parent = next(row for row in response.data if row["id"] == self.ids[0])
        self.assertEqual(parent["children"][0]["id"], self.ids[1])
        self.assertEqual(parent["children"][0]["home_featured_order"], 2)

    def test_permissions_reject_customer_anonymous_and_view_only(self):
        self.api.force_authenticate(None)
        self.assertIn(self.choose().status_code, [401, 403])
        self.api.force_authenticate(self.admin, token={"purpose": "customer"})
        self.assertEqual(self.choose().status_code, 403)
        staff = get_user_model().objects.create_user(phone="09123456781", is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename="view_category"))
        self.api.force_authenticate(staff, token={"purpose": "management"})
        self.assertEqual(
            self.api.get("/api/v1/owner/category-showcase/").status_code, 200
        )
        self.assertEqual(self.choose().status_code, 403)
        self.assertEqual(
            self.api.put(
                f"/api/v1/owner/category-images/{self.ids[0]}/",
                {"image": self.image()},
                format="multipart",
            ).status_code,
            403,
        )

    def test_upload_is_normalized_and_returned_in_dashboard(self):
        response = self.api.put(
            f"/api/v1/owner/category-images/{self.ids[0]}/",
            {"image": self.image()},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.data)
        row = Category.objects.get(pk=self.ids[0])
        self.assertTrue(row.image.name.endswith(".webp"))
        with row.image.open() as file:
            self.assertEqual(Image.open(file).format, "WEBP")
        self.assertIn("image_url", response.data)
        rows = self.api.get("/api/v1/owner/categories/").data["results"]
        self.assertTrue(next(r for r in rows if r["id"] == row.pk)["image_url"])

    def test_fake_and_oversize_uploads_rejected(self):
        for file in [
            SimpleUploadedFile("fake.png", b"not an image"),
            self.image("file.svg"),
            SimpleUploadedFile("huge.png", b"x" * (5 * 1024 * 1024 + 1)),
        ]:
            response = self.api.put(
                f"/api/v1/owner/category-images/{self.ids[0]}/",
                {"image": file},
                format="multipart",
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(list(Path(self.tmp.name).rglob("*.webp")), [])

    def test_deleting_selected_image_is_rejected(self):
        self.choose()
        self.assertEqual(
            self.api.delete(
                f"/api/v1/owner/category-images/{self.ids[0]}/"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.api.delete(
                f"/api/v1/owner/category-images/{self.rows[6].pk}/"
            ).status_code,
            200,
        )

    def test_failed_image_write_rolls_back_and_cleans_uploaded_file(self):
        with patch(
            "django.contrib.admin.options.ModelAdmin.log_change",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.api.put(
                    f"/api/v1/owner/category-images/{self.ids[0]}/",
                    {"image": self.image()},
                    format="multipart",
                )
        self.assertEqual(
            Category.objects.get(pk=self.ids[0]).image.name, "categories/0.webp"
        )
        self.assertEqual(list(Path(self.tmp.name).rglob("*.webp")), [])

    def test_failed_home_audit_does_not_publish_partial_selection(self):
        with patch(
            "django.contrib.admin.options.ModelAdmin.log_change",
            side_effect=RuntimeError("audit failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.choose()
        self.assertFalse(Category.objects.filter(is_home_featured=True).exists())
