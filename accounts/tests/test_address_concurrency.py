from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection

from accounts.models import Address
from accounts.services.profile_service import create_address

User = get_user_model()


@pytest.mark.django_db(transaction=True)
def test_concurrent_default_addresses_leave_one_default():
    if connection.vendor != "postgresql":
        pytest.skip("This concurrency test requires PostgreSQL.")

    user = User.objects.create_user(phone="09320000001")
    user_id = user.pk
    barrier = Barrier(2)

    def create_one(number):
        close_old_connections()

        try:
            current_user = User.objects.get(pk=user_id)
            barrier.wait(timeout=10)

            address = create_address(
                current_user,
                {
                    "recipient_name": "Concurrent Test",
                    "recipient_phone": "09123456789",
                    "province": "قزوین",
                    "city": "محمدیه",
                    "street_address": f"نشانی آزمایشی {number}",
                    "building_number": str(number),
                    "unit": "",
                    "postal_code": "1234567890",
                    "is_default": True,
                },
            )
            return address.pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(create_one, [1, 2]))

    assert len(set(results)) == 2
    assert Address.objects.filter(user_id=user_id).count() == 2
    assert Address.objects.filter(
        user_id=user_id,
        is_default=True,
    ).count() == 1