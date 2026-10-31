from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import SavedProduct
from cms.models import SiteFooter
from cms.services.footer_service import DEFAULT_FOOTER
from orders.models import (
    Order,
    OrderEvent,
    OrderItem,
    ReturnRequest,
    Shipment,
    StoreSettings,
)
from products.models import Category, Product

User = get_user_model()


class CustomerHubTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(phone="09123456789")
        self.other = User.objects.create_user(phone="09123456788")
        self.admin = User.objects.create_superuser(phone="09123456787", password="test")
        self.api = APIClient()
        self.login()
        Category.objects.bulk_create([Category(name="Test", slug="test")])
        self.category = Category.objects.get(slug="test")
        self.product = Product.objects.create(
            category=self.category,
            name="Test product",
            slug="test-product",
            price=1000,
            stock=4,
        )
        StoreSettings.objects.create(
            shipping_cost=100, returns_enabled=True, return_days=7
        )

    def login(self, user=None, purpose="customer"):
        self.api.force_authenticate(user=user or self.user, token={"purpose": purpose})

    def order(self, user=None, status="delivered", days=1):
        now = timezone.now()
        row = Order.objects.create(
            user=user or self.user,
            request_id=uuid4(),
            request_fingerprint="a" * 64,
            status=status,
            recipient_name="Test",
            recipient_phone="09123456789",
            province="P",
            city="C",
            street_address="Street",
            building_number="1",
            postal_code="1234567890",
            subtotal=2000,
            shipping_cost=100,
            total=2100,
            expires_at=now + timedelta(hours=2),
            paid_at=now - timedelta(days=days),
            delivered_at=now - timedelta(days=days) if status == "delivered" else None,
        )
        item = OrderItem.objects.create(
            order=row,
            product=self.product,
            selection_key=f"p:{self.product.pk}",
            product_name="Test product",
            product_slug="test-product",
            quantity=2,
            unit_price=1000,
            line_total=2000,
        )
        return row, item

    def payload(self, order, item, quantity=1):
        return {
            "order_id": str(order.pk),
            "reason": "Damaged",
            "items": [{"item_id": item.pk, "quantity": quantity}],
        }

    def test_anonymous_is_denied(self):
        self.api.force_authenticate(user=None)
        for endpoint in ["summary/", "orders/", "saved/", "returns/"]:
            with self.subTest(endpoint=endpoint):
                self.assertEqual(
                    self.api.get("/api/v1/customer/" + endpoint).status_code, 401
                )

    def test_management_session_is_denied_customer_api(self):
        self.login(self.admin, "management")
        self.assertEqual(self.api.get("/api/v1/customer/summary/").status_code, 403)

    def test_foreign_order_is_not_visible(self):
        row, _ = self.order(self.other)
        self.assertEqual(
            self.api.get(f"/api/v1/customer/orders/{row.pk}/").status_code, 404
        )
        self.assertEqual(self.api.get("/api/v1/customer/orders/").data["count"], 0)

    def test_summary_counts_and_recent_are_owned(self):
        self.order(status="paid")
        self.order(status="delivered")
        self.order(self.other, status="paid")
        response = self.api.get("/api/v1/customer/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["counts"]["paid"], 1)
        self.assertEqual(response.data["counts"]["delivered"], 1)
        self.assertEqual(len(response.data["recent_orders"]), 2)
        self.assertIn("no-store", response["Cache-Control"])

    def test_filter_and_invalid_status(self):
        self.order(status="paid")
        self.order(status="delivered")
        self.assertEqual(
            self.api.get("/api/v1/customer/orders/?status=paid").data["count"], 1
        )
        self.assertEqual(
            self.api.get("/api/v1/customer/orders/?status=invalid").status_code, 400
        )

    def test_saved_is_idempotent_and_private(self):
        payload = {"product_id": self.product.pk, "kind": "favorite", "enabled": True}
        for _ in range(2):
            self.assertEqual(
                self.api.post(
                    "/api/v1/customer/saved/", payload, format="json"
                ).status_code,
                200,
            )
        self.assertEqual(SavedProduct.objects.count(), 1)
        self.login(self.other)
        self.assertEqual(self.api.get("/api/v1/customer/saved/").data["count"], 0)
        self.assertFalse(
            self.api.get(f"/api/v1/customer/saved/{self.product.pk}/").data["favorite"]
        )

    def test_saved_kinds_are_separate_and_inactive_can_be_removed(self):
        for kind in ["favorite", "later"]:
            self.api.post(
                "/api/v1/customer/saved/",
                {"product_id": self.product.pk, "kind": kind, "enabled": True},
                format="json",
            )
        self.product.is_active = False
        self.product.save()
        row = self.api.get("/api/v1/customer/saved/?kind=favorite").data["results"][0]
        self.assertFalse(row["public"])
        self.assertIsNone(row["price"])
        self.assertEqual(row["name"], "کالای خارج از دسترس")
        response = self.api.post(
            "/api/v1/customer/saved/",
            {"product_id": self.product.pk, "kind": "favorite", "enabled": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SavedProduct.objects.get().kind, "later")

    def test_cannot_save_draft_or_invalid_kind(self):
        self.product.status = "draft"
        self.product.save()
        response = self.api.post(
            "/api/v1/customer/saved/",
            {"product_id": self.product.pk, "kind": "favorite", "enabled": True},
            format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.api.get("/api/v1/customer/saved/?kind=wrong").status_code, 400
        )

    def test_saved_pagination(self):
        for n in range(14):
            p = Product.objects.create(
                category=self.category, name=f"P{n}", slug=f"p{n}", price=1000, stock=2
            )
            SavedProduct.objects.create(user=self.user, product=p, kind="favorite")
        response = self.api.get("/api/v1/customer/saved/")
        self.assertEqual(response.data["count"], 14)
        self.assertEqual(len(response.data["results"]), 12)
        self.assertIsNotNone(response.data["next"])

    def test_return_creation_idempotency_and_no_stock_change(self):
        row, item = self.order()
        payload = self.payload(row, item)
        self.assertEqual(
            self.api.post(
                "/api/v1/customer/returns/", payload, format="json"
            ).status_code,
            201,
        )
        self.assertEqual(
            self.api.post(
                "/api/v1/customer/returns/", payload, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(ReturnRequest.objects.count(), 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        payload["reason"] = "Changed"
        self.assertEqual(
            self.api.post(
                "/api/v1/customer/returns/", payload, format="json"
            ).status_code,
            400,
        )
        self.assertFalse(
            self.api.get(f"/api/v1/customer/orders/{row.pk}/").data[
                "can_request_return"
            ]
        )

    def test_foreign_order_cannot_be_returned(self):
        row, item = self.order(self.other)
        self.assertEqual(
            self.api.post(
                "/api/v1/customer/returns/", self.payload(row, item), format="json"
            ).status_code,
            404,
        )

    def test_foreign_item_and_excess_quantity_and_duplicates_rejected(self):
        row, item = self.order()
        other, other_item = self.order(self.other)
        for items in [
            [{"item_id": other_item.pk, "quantity": 1}],
            [{"item_id": item.pk, "quantity": 3}],
            [{"item_id": item.pk, "quantity": 1}] * 2,
        ]:
            with self.subTest(items=items):
                payload = self.payload(row, item)
                payload["items"] = items
                self.assertEqual(
                    self.api.post(
                        "/api/v1/customer/returns/", payload, format="json"
                    ).status_code,
                    400,
                )
        self.assertFalse(ReturnRequest.objects.exists())

    def test_return_window_and_delivery_required(self):
        for status, days in [("paid", 1), ("shipped", 1), ("delivered", 9)]:
            with self.subTest(status=status, days=days):
                row, item = self.order(status=status, days=days)
                self.assertEqual(
                    self.api.post(
                        "/api/v1/customer/returns/",
                        self.payload(row, item),
                        format="json",
                    ).status_code,
                    400,
                )

    def test_disabled_returns_and_missing_delivery_timestamp(self):
        StoreSettings.objects.update(returns_enabled=False)
        row, item = self.order()
        self.assertEqual(
            self.api.post(
                "/api/v1/customer/returns/", self.payload(row, item), format="json"
            ).status_code,
            400,
        )
        StoreSettings.objects.update(returns_enabled=True)
        row.delivered_at = None
        row.save()
        self.assertEqual(
            self.api.post(
                "/api/v1/customer/returns/", self.payload(row, item), format="json"
            ).status_code,
            400,
        )

    def test_return_reason_and_items_required(self):
        row, item = self.order()
        for extra in [
            {"reason": ""},
            {"items": []},
            {"items": [{"item_id": item.pk, "quantity": 0}]},
        ]:
            payload = self.payload(row, item)
            payload.update(extra)
            self.assertEqual(
                self.api.post(
                    "/api/v1/customer/returns/", payload, format="json"
                ).status_code,
                400,
            )

    def test_only_owner_can_read_return_requests(self):
        row, item = self.order()
        self.api.post(
            "/api/v1/customer/returns/", self.payload(row, item), format="json"
        )
        self.login(self.other)
        self.assertEqual(self.api.get("/api/v1/customer/returns/").data["count"], 0)

    def test_customer_cannot_change_order_or_policy(self):
        row, _ = self.order(status="paid")
        self.assertEqual(
            self.api.post(
                "/api/v1/owner/customer-operations/",
                {
                    "order_id": str(row.pk),
                    "expected_status": "paid",
                    "status": "shipped",
                    "carrier": "Post",
                    "tracking_code": "A",
                },
                format="json",
            ).status_code,
            403,
        )

    def test_shipment_requires_tracking_and_paid_order(self):
        row, _ = self.order(status="paid")
        self.login(self.admin, "management")
        payload = {
            "order_id": str(row.pk),
            "expected_status": "paid",
            "status": "shipped",
            "carrier": "Post",
            "tracking_code": "",
        }
        self.assertEqual(
            self.api.post(
                "/api/v1/owner/customer-operations/", payload, format="json"
            ).status_code,
            400,
        )
        payload.update(tracking_code="ABC", tracking_url="http://example.com")
        self.assertEqual(
            self.api.post(
                "/api/v1/owner/customer-operations/", payload, format="json"
            ).status_code,
            400,
        )
        self.assertFalse(Shipment.objects.exists())

    def test_shipment_delivery_and_stale_transition(self):
        row, _ = self.order(status="paid")
        self.login(self.admin, "management")
        payload = {
            "order_id": str(row.pk),
            "expected_status": "paid",
            "status": "shipped",
            "carrier": "Post",
            "tracking_code": "ABC",
            "tracking_url": "https://example.com/track",
        }
        self.assertEqual(
            self.api.post(
                "/api/v1/owner/customer-operations/", payload, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.api.post(
                "/api/v1/owner/customer-operations/", payload, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(OrderEvent.objects.count(), 1)
        self.assertEqual(
            self.api.post(
                "/api/v1/owner/customer-operations/",
                {
                    "order_id": str(row.pk),
                    "expected_status": "shipped",
                    "status": "delivered",
                },
                format="json",
            ).status_code,
            200,
        )
        self.login()
        data = self.api.get(f"/api/v1/customer/orders/{row.pk}/").data
        self.assertEqual(data["shipment"]["tracking_code"], "ABC")
        self.assertEqual(len(data["events"]), 4)
        self.assertTrue(data["can_request_return"])

    def test_return_review_transitions_and_note(self):
        row, item = self.order()
        self.api.post(
            "/api/v1/customer/returns/", self.payload(row, item), format="json"
        )
        returned = ReturnRequest.objects.get()
        self.login(self.admin, "management")
        path = "/api/v1/owner/customer-operations/"
        payload = {
            "request_id": returned.pk,
            "expected_status": "requested",
            "status": "approved",
            "note": "",
        }
        self.assertEqual(self.api.patch(path, payload, format="json").status_code, 400)
        payload["note"] = "Send the item"
        self.assertEqual(self.api.patch(path, payload, format="json").status_code, 200)
        self.assertEqual(self.api.patch(path, payload, format="json").status_code, 400)
        payload.update(expected_status="approved", status="received", note="Received")
        self.assertEqual(self.api.patch(path, payload, format="json").status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        row.refresh_from_db()
        self.assertEqual(row.status, "delivered")

    def test_staff_without_permissions_is_denied(self):
        self.other.is_staff = True
        self.other.save()
        self.login(self.other, "management")
        self.assertEqual(
            self.api.get("/api/v1/owner/customer-operations/").status_code, 403
        )
        self.assertEqual(
            self.api.get("/api/v1/owner/footer-settings/").status_code, 403
        )

    def test_policy_bounds(self):
        self.login(self.admin, "management")
        path = "/api/v1/owner/customer-operations/"
        for days in [0, 366]:
            self.assertEqual(
                self.api.patch(
                    path, {"enabled": True, "days": days}, format="json"
                ).status_code,
                400,
            )
        self.assertEqual(
            self.api.patch(
                path, {"enabled": True, "days": 14}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(StoreSettings.objects.get().return_days, 14)

    def test_public_footer_read_and_no_implicit_row_creation(self):
        self.api.force_authenticate(user=None)
        response = self.api.get("/api/v1/content/footer/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "دیجی‌شاپ")
        self.assertFalse(SiteFooter.objects.exists())
        self.assertEqual(
            self.api.get("/pages-assets/store-footer.css").status_code, 200
        )

    def test_footer_update_revision_and_safe_urls(self):
        self.login(self.admin, "management")
        path = "/api/v1/owner/footer-settings/"
        config = deepcopy(DEFAULT_FOOTER)
        config["name"] = "My shop"
        response = self.api.patch(
            path, {"revision": 1, "config": config}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            self.api.get("/api/v1/content/footer/").json()["name"], "My shop"
        )
        self.assertEqual(
            self.api.patch(
                path, {"revision": 1, "config": config}, format="json"
            ).status_code,
            400,
        )
        config["columns"][0]["links"][0]["url"] = "javascript:alert(1)"
        self.assertEqual(
            self.api.patch(
                path, {"revision": 2, "config": config}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(SiteFooter.objects.get().revision, 2)

    def test_footer_validation_and_customer_denied(self):
        config = deepcopy(DEFAULT_FOOTER)
        config["email"] = "bad"
        self.assertEqual(
            self.api.patch(
                "/api/v1/owner/footer-settings/",
                {"revision": 1, "config": config},
                format="json",
            ).status_code,
            403,
        )
        self.login(self.admin, "management")
        self.assertEqual(
            self.api.patch(
                "/api/v1/owner/footer-settings/",
                {"revision": 1, "config": config},
                format="json",
            ).status_code,
            400,
        )

    def test_dashboard_discovers_new_resources(self):
        self.login(self.admin, "management")
        response = self.api.get("/api/v1/owner/")
        self.assertEqual(response.status_code, 200)
        keys = {row["key"] for row in response.data["resources"]}
        self.assertIn("footer", keys)
        self.assertIn("customer-operations", keys)
