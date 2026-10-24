import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse

from products.api.v1.serializers import ProductSerializer
from products.models import (
    Attribute,
    Brand,
    Category,
    CategoryAttribute,
    Product,
    ProductAttributeValue,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup_data():
    phones = Category.objects.create(name="Phones", slug="phones")
    laptops = Category.objects.create(name="Laptops", slug="laptops")

    color = Attribute.objects.create(name="Color", slug="color")
    ram = Attribute.objects.create(name="RAM", slug="ram")

    CategoryAttribute.objects.create(
        category=phones,
        attribute=color,
    )
    CategoryAttribute.objects.create(
        category=laptops,
        attribute=ram,
    )

    brand = Brand.objects.create(name="Apple", slug="apple")

    product = Product.objects.create(
        category=phones,
        brand=brand,
        name="iPhone 16",
        slug="iphone-16",
        price=60000000,
        is_active=False,
    )

    return {
        "phones": phones,
        "laptops": laptops,
        "color": color,
        "ram": ram,
        "brand": brand,
        "product": product,
    }


def test_product_can_have_brand(setup_data):
    product = setup_data["product"]

    assert product.brand.name == "Apple"
    assert str(product.brand) == "Apple"


def test_category_has_its_own_attributes(setup_data):
    phones = setup_data["phones"]
    color = setup_data["color"]
    ram = setup_data["ram"]

    assert CategoryAttribute.objects.filter(
        category=phones,
        attribute=color,
    ).exists()

    assert not CategoryAttribute.objects.filter(
        category=phones,
        attribute=ram,
    ).exists()


def test_product_accepts_allowed_attribute(setup_data):
    product = setup_data["product"]
    color = setup_data["color"]

    value = ProductAttributeValue(
        product=product,
        attribute=color,
        value="Black",
    )

    value.full_clean()
    value.save()

    assert product.attribute_values.get(attribute=color).value == "Black"


def test_product_rejects_invalid_attribute(setup_data):
    product = setup_data["product"]
    ram = setup_data["ram"]

    value = ProductAttributeValue(
        product=product,
        attribute=ram,
        value="16GB",
    )

    with pytest.raises(ValidationError):
        value.full_clean()


def test_duplicate_category_attribute_is_rejected(setup_data):
    phones = setup_data["phones"]
    color = setup_data["color"]

    with pytest.raises(IntegrityError), transaction.atomic():
        CategoryAttribute.objects.create(
            category=phones,
            attribute=color,
        )


def test_duplicate_product_attribute_is_rejected(setup_data):
    product = setup_data["product"]
    color = setup_data["color"]

    ProductAttributeValue.objects.create(
        product=product,
        attribute=color,
        value="Black",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        ProductAttributeValue.objects.create(
            product=product,
            attribute=color,
            value="White",
        )


def test_admin_rejects_incompatible_category_change(
    admin_client, setup_data
):
    product = setup_data["product"]
    laptops = setup_data["laptops"]
    color = setup_data["color"]

    ProductAttributeValue.objects.create(
        product=product,
        attribute=color,
        value="Black",
    )

    response = admin_client.get(
        reverse("admin:products_product_change", args=[product.pk])
    )

    form_class = type(response.context["adminform"].form)

    form = form_class(
        data={
            "category": str(laptops.pk),
            "brand": str(product.brand_id),
            "name": product.name,
            "slug": product.slug,
            "price": str(product.price),
            "stock": str(product.stock),
            "is_active": "",
        },
        instance=product,
    )

    assert not form.is_valid()
    assert any(
        "مشخصاتی دارد" in error
        for error in form.non_field_errors()
    )


def test_product_api_includes_brand_and_attributes(setup_data):
    product = setup_data["product"]
    color = setup_data["color"]

    ProductAttributeValue.objects.create(
        product=product,
        attribute=color,
        value="Black",
    )

    data = ProductSerializer(product).data

    assert data["brand"]["name"] == "Apple"
    assert data["brand"]["slug"] == "apple"
    assert data["attribute_values"][0]["attribute"] == "Color"
    assert data["attribute_values"][0]["value"] == "Black"