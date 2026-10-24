import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from products.api.v1.serializers import ProductSerializer
from products.models import Category, Product, ProductVariant
from products.services.variant_service import (
    get_default_variant,
    is_product_available,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    category = Category.objects.create(
        name="موبایل",
        slug="mobile",
    )

    return Product.objects.create(
        category=category,
        name="iPhone 16",
        slug="iphone-16",
        price=60_000_000,
        stock=0,
        is_active=True,
    )


def create_variant(product, sku, color, storage, price, stock, active=True):
    return ProductVariant.objects.create(
        product=product,
        sku=sku,
        color=color,
        storage=storage,
        price=price,
        stock=stock,
        is_active=active,
    )


def test_product_can_have_multiple_variants(product):
    create_variant(product, "IPH-BLK-128", "Black", "128GB", 60_000_000, 5)
    create_variant(product, "IPH-BLK-256", "Black", "256GB", 70_000_000, 3)

    assert product.variants.count() == 2


def test_duplicate_variant_combination_is_rejected(product):
    create_variant(product, "SKU-1", "Black", "128GB", 60_000_000, 5)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_variant(product, "SKU-2", "Black", "128GB", 65_000_000, 3)


def test_duplicate_sku_is_rejected(product):
    create_variant(product, "SKU-1", "Black", "128GB", 60_000_000, 5)

    with pytest.raises(IntegrityError), transaction.atomic():
        create_variant(product, "SKU-1", "White", "128GB", 62_000_000, 2)


def test_variant_requires_color_or_storage(product):
    variant = ProductVariant(
        product=product,
        sku="SKU-1",
        color="",
        storage="",
        price=60_000_000,
        stock=5,
    )

    with pytest.raises(ValidationError):
        variant.full_clean()


def test_variant_rejects_zero_price(product):
    variant = ProductVariant(
        product=product,
        sku="SKU-1",
        color="Black",
        storage="128GB",
        price=0,
        stock=5,
    )

    with pytest.raises(ValidationError):
        variant.full_clean()


def test_default_variant_is_cheapest_available(product):
    expensive = create_variant(
        product, "SKU-1", "Black", "256GB", 70_000_000, 3
    )
    cheapest = create_variant(
        product, "SKU-2", "Black", "128GB", 60_000_000, 5
    )
    create_variant(
        product, "SKU-3", "White", "128GB", 58_000_000, 0
    )

    assert get_default_variant(product) == cheapest
    assert get_default_variant(product) != expensive


def test_default_variant_ignores_inactive_variants(product):
    create_variant(
        product, "SKU-1", "Black", "128GB", 50_000_000, 5, active=False
    )
    active = create_variant(
        product, "SKU-2", "White", "128GB", 60_000_000, 2
    )

    assert get_default_variant(product) == active


def test_product_without_available_variant_is_unavailable(product):
    create_variant(product, "SKU-1", "Black", "128GB", 60_000_000, 0)

    assert get_default_variant(product) is None
    assert is_product_available(product) is False


def test_product_with_available_variant_is_available(product):
    create_variant(product, "SKU-1", "Black", "128GB", 60_000_000, 2)

    assert is_product_available(product) is True


def test_inactive_product_is_unavailable(product):
    create_variant(product, "SKU-1", "Black", "128GB", 60_000_000, 2)
    product.is_active = False
    product.save(update_fields=["is_active"])

    assert is_product_available(product) is False


def test_simple_product_uses_own_stock(product):
    product.stock = 4
    product.save(update_fields=["stock"])

    assert is_product_available(product) is True


def test_api_hides_inactive_variants(product):
    create_variant(
        product, "SKU-1", "Black", "128GB", 60_000_000, 5
    )
    create_variant(
        product, "SKU-2", "White", "256GB", 70_000_000, 2, active=False
    )

    data = ProductSerializer(product).data

    assert len(data["variants"]) == 1
    assert data["variants"][0]["sku"] == "SKU-1"


def test_api_returns_default_variant_and_availability(product):
    create_variant(
        product, "SKU-1", "Black", "128GB", 60_000_000, 5
    )

    data = ProductSerializer(product).data

    assert data["default_variant"]["sku"] == "SKU-1"
    assert data["is_available"] is True