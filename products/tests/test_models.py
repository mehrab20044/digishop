import pytest
from products.models import Category, Product
from django.db import IntegrityError

@pytest.mark.django_db
def test_category_str():
    category = Category.objects.create(
        name= "Keyboards",
        slug = "keyboards",
    )

    assert str(category) == "Keyboards"


@pytest.mark.django_db
def test_product_str():
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    product = Product.objects.create(
        category=category,
        name="Logitech K580",
        slug="logitech-k580",
        price=4700000,
        stock=10,
    )

    assert str(product) == "Logitech K580"



@pytest.mark.django_db
def test_product_slug_must_be_unique():
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    Product.objects.create(
        category=category,
        name="Logitech K580",
        slug="logitech-k580",
        price=4700000,
    )

    with pytest.raises(IntegrityError):
        Product.objects.create(
            category=category,
            name="Another Logitech",
            slug="logitech-k580",
            price=3000000,
        )

@pytest.mark.django_db
def test_category_slug_must_be_unique():
    Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    with pytest.raises(IntegrityError):
        Category.objects.create(
            name="Computer Accessories",
            slug="keyboards",
        )