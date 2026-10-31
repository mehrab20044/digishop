from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest import skipUnless
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from orders.models import Order, OrderEvent, OrderItem, ReturnRequest, StoreSettings
from orders.services.customer_hub_service import advance_order, request_return


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL row locks")
class CustomerHubConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(phone="09123456781")
        self.actor = get_user_model().objects.create_superuser(
            phone="09123456782", password="test"
        )
        StoreSettings.objects.create(
            shipping_cost=100, returns_enabled=True, return_days=7
        )
        now = timezone.now()
        self.order = Order.objects.create(
            user=self.user,
            request_id=uuid4(),
            request_fingerprint="a" * 64,
            status="delivered",
            recipient_name="A",
            recipient_phone=self.user.phone,
            province="P",
            city="C",
            street_address="S",
            building_number="1",
            postal_code="1234567890",
            subtotal=1000,
            shipping_cost=100,
            total=1100,
            expires_at=now + timedelta(hours=2),
            delivered_at=now,
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            selection_key="demo",
            product_name="P",
            product_slug="p",
            quantity=1,
            unit_price=1000,
            line_total=1000,
        )

    def test_duplicate_return_is_one_record(self):
        def run(_):
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                row, created = request_return(
                    user,
                    self.order.pk,
                    "Damage",
                    [{"item_id": self.item.pk, "quantity": 1}],
                )
                return row.pk, created
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(ReturnRequest.objects.count(), 1)
        self.assertEqual(len({pk for pk, created in results}), 1)
        self.assertEqual(sum(created for pk, created in results), 1)

    def test_status_transition_is_applied_once(self):
        Order.objects.filter(pk=self.order.pk).update(status="paid", delivered_at=None)

        def run(_):
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.actor.pk)
                try:
                    advance_order(
                        actor,
                        self.order.pk,
                        "paid",
                        "shipped",
                        carrier="Post",
                        tracking_code="ABC",
                    )
                    return True
                except ValidationError:
                    return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(OrderEvent.objects.filter(order=self.order).count(), 1)
