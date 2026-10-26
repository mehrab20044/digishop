import pytest


@pytest.fixture
def admin_user(db, django_user_model):
    return django_user_model.objects.create_superuser(
        phone="09300000001",
        password="TestAdminPassword123!",
    )
