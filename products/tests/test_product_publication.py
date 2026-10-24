import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from products.models import Category, Product, ProductVariant
from products.services.product_service import ProductService
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
        name="Test iPhone",
        slug="test-iphone",
        price=60_000_000,
        stock=5,
        is_active=True,
        status=Product.Status.PUBLISHED,
    )


def create_variant(product, sku, price, stock, active=True):
    return ProductVariant.objects.create(
        product=product,
        sku=sku,
        color="Black",
        storage=sku,
        price=price,
        stock=stock,
        is_active=active,
    )


def test_product_is_published_by_default(product):
    assert product.status == Product.Status.PUBLISHED


def test_draft_product_is_hidden_from_public_queryset(product):
    product.status = Product.Status.DRAFT
    product.save(update_fields=["status"])

    assert not ProductService.get_active_products().filter(
        pk=product.pk
    ).exists()


def test_published_product_is_visible_in_public_queryset(product):
    assert ProductService.get_active_products().filter(
        pk=product.pk
    ).exists()


def test_inactive_product_is_hidden(product):
    product.is_active = False
    product.save(update_fields=["is_active"])

    assert not ProductService.get_active_products().filter(
        pk=product.pk
    ).exists()


def test_published_simple_product_rejects_zero_price(product):
    product.price = 0

    with pytest.raises(ValidationError):
        product.full_clean()


def test_draft_product_accepts_zero_price(product):
    product.status = Product.Status.DRAFT
    product.price = 0

    product.full_clean()


def test_draft_product_is_not_available(product):
    product.status = Product.Status.DRAFT
    product.save(update_fields=["status"])

    assert is_product_available(product) is False


def test_simple_product_without_stock_is_unavailable(product):
    product.stock = 0
    product.save(update_fields=["stock"])

    assert is_product_available(product) is False


def test_variant_product_with_valid_stock_is_available(product):
    create_variant(product, "SKU-1", 60_000_000, 3)

    assert is_product_available(product) is True


def test_variant_product_with_zero_stock_is_unavailable(product):
    create_variant(product, "SKU-1", 60_000_000, 0)

    assert is_product_available(product) is False


def test_invalid_variant_price_is_not_available(product):
    create_variant(product, "SKU-1", 0, 5)

    assert is_product_available(product) is False
    assert get_default_variant(product) is None


def test_default_variant_is_none_for_draft_product(product):
    create_variant(product, "SKU-1", 60_000_000, 5)
    product.status = Product.Status.DRAFT
    product.save(update_fields=["status"])

    assert get_default_variant(product) is None


def test_draft_product_detail_returns_404(client, product):
    product.status = Product.Status.DRAFT
    product.save(update_fields=["status"])

    response = client.get(
        reverse("products:product-detail", args=[product.pk])
    )

    assert response.status_code == 404