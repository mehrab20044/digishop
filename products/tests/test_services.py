import pytest

from products.models import Category, Product
from products.services.product_service import ProductService


@pytest.mark.django_db
def test_get_active_products_excludes_inactive():
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    active_product = Product.objects.create(
        category=category,
        name="Logitech K580",
        slug="logitech-k580",
        price=4700000,
        is_active=True,
    )

    Product.objects.create(
        category=category,
        name="Inactive Keyboard",
        slug="inactive-keyboard",
        price=2000000,
        is_active=False,
    )

    products = ProductService.get_active_products()

    assert products.count() == 1
    assert products.first() == active_product



@pytest.mark.django_db
def test_get_categories_ordered_by_name():
    Category.objects.create(
        name="Mice",
        slug="mice",
    )

    Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    Category.objects.create(
        name="Monitors",
        slug="monitors",
    )

    categories = ProductService.get_categories()

    assert list(categories.values_list("name", flat=True)) == [
        "Keyboards",
        "Mice",
        "Monitors",
    ]


@pytest.mark.django_db
def test_get_active_products_ordered_by_created_at():
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    older_product = Product.objects.create(
        category=category,
        name="Older Keyboard",
        slug="older-keyboard",
        price=2000000,
    )

    newer_product = Product.objects.create(
        category=category,
        name="Newer Keyboard",
        slug="newer-keyboard",
        price=4000000,
    )

    products = ProductService.get_active_products()

    assert list(products) == [
        newer_product,
        older_product,
    ]