import pytest

from products.models import Category, Product, ProductVariant


@pytest.mark.django_db
def test_product_list_returns_active_products(client):
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    active_product = Product.objects.create(
        category=category,
        name="Logitech K580",
        slug="logitech-k580",
        price=4700000,
        stock=10,
        is_active=True,
    )

    Product.objects.create(
        category=category,
        name="Inactive Keyboard",
        slug="inactive-keyboard",
        price=2000000,
        is_active=False,
    )

    response = client.get(
        "/products/api/v1/products/",
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["id"] == active_product.id
    assert data["results"][0]["name"] == "Logitech K580"


@pytest.mark.django_db
def test_product_detail_returns_active_product(client):
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
        is_active=True,
    )

    response = client.get(
        f"/products/api/v1/products/{product.pk}/",
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == product.pk
    assert data["name"] == "Logitech K580"
    assert data["category"]["name"] == "Keyboards"


@pytest.mark.django_db
def test_inactive_product_detail_returns_404(client):
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    product = Product.objects.create(
        category=category,
        name="Inactive Keyboard",
        slug="inactive-keyboard",
        price=2000000,
        is_active=False,
    )

    response = client.get(
        f"/products/api/v1/products/{product.pk}/",
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 404

    data = response.json()

    assert data["success"] is False
    assert data["error"]["code"] == "not_found"

@pytest.mark.django_db
def test_categories_api_returns_categories(client):
    Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    Category.objects.create(
        name="Monitors",
        slug="monitors",
    )

    response = client.get(
        "/products/api/v1/categories/",
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 2

    assert [category["name"] for category in data["results"]] == [
        "Keyboards",
        "Monitors",
    ]


@pytest.mark.django_db
def test_product_search_by_name(client):
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

    Product.objects.create(
        category=category,
        name="Rapoo K2600",
        slug="rapoo-k2600",
        price=2000000,
    )

    response = client.get(
        "/products/api/v1/products/",
        {"search": "Logitech"},
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "Logitech K580"


@pytest.mark.django_db
def test_product_filter_by_category(client):
    keyboards = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    monitors = Category.objects.create(
        name="Monitors",
        slug="monitors",
    )

    Product.objects.create(
        category=keyboards,
        name="Logitech K580",
        slug="logitech-k580",
        price=4700000,
    )

    Product.objects.create(
        category=monitors,
        name="LG Monitor",
        slug="lg-monitor",
        price=12000000,
    )

    response = client.get(
        "/products/api/v1/products/",
        {"category": keyboards.pk},
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "Logitech K580"
    assert data["results"][0]["category"]["id"] == keyboards.pk



@pytest.mark.django_db
def test_product_filter_by_price_range(client):
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    Product.objects.create(
        category=category,
        name="Rapoo K2600",
        slug="rapoo-k2600",
        price=2000000,
    )

    Product.objects.create(
        category=category,
        name="Logitech K580",
        slug="logitech-k580",
        price=4700000,
    )

    Product.objects.create(
        category=category,
        name="Logitech MX Keys",
        slug="logitech-mx-keys",
        price=8500000,
    )

    response = client.get(
        "/products/api/v1/products/",
        {
            "min_price": 3000000,
            "max_price": 6000000,
        },
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "Logitech K580"
    assert data["results"][0]["price"] == 4700000


@pytest.mark.django_db
def test_product_filter_by_stock(client):
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    Product.objects.create(
        category=category,
        name="Logitech K580",
        slug="logitech-k580",
        price=4700000,
        stock=10,
    )

    Product.objects.create(
        category=category,
        name="Rapoo K2600",
        slug="rapoo-k2600",
        price=2000000,
        stock=0,
    )

    response = client.get(
        "/products/api/v1/products/",
        {"in_stock": "true"},
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert len(data["results"]) == 1
    assert data["results"][0]["name"] == "Logitech K580"
    assert data["results"][0]["stock"] == 10


@pytest.mark.django_db
def test_product_ordering_by_price(client):
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    Product.objects.create(
        category=category,
        name="Expensive Keyboard",
        slug="expensive-keyboard",
        price=8000000,
    )

    Product.objects.create(
        category=category,
        name="Cheap Keyboard",
        slug="cheap-keyboard",
        price=2000000,
    )

    Product.objects.create(
        category=category,
        name="Medium Keyboard",
        slug="medium-keyboard",
        price=4500000,
    )

    response = client.get(
        "/products/api/v1/products/",
        {"ordering": "effective_price"},
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert [product["price"] for product in data["results"]] == [
        2000000,
        4500000,
        8000000,
    ]


@pytest.mark.django_db
def test_product_ordering_by_price_descending(client):
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    Product.objects.create(
        category=category,
        name="Cheap Keyboard",
        slug="cheap-keyboard",
        price=2000000,
    )

    Product.objects.create(
        category=category,
        name="Expensive Keyboard",
        slug="expensive-keyboard",
        price=8000000,
    )

    Product.objects.create(
        category=category,
        name="Medium Keyboard",
        slug="medium-keyboard",
        price=4500000,
    )

    response = client.get(
        "/products/api/v1/products/",
        {"ordering": "-effective_price"},
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 3
    assert [product["price"] for product in data["results"]] == [
        8000000,
        4500000,
        2000000,
    ]

@pytest.mark.django_db
def test_product_pagination(client):
    category = Category.objects.create(
        name="Keyboards",
        slug="keyboards",
    )

    for i in range(15):
        Product.objects.create(
            category=category,
            name=f"Keyboard {i}",
            slug=f"keyboard-{i}",
            price=1000000 + i * 100000,
        )

    response = client.get(
        "/products/api/v1/products/",
        {"page": 1},
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 15
    assert len(data["results"]) == 12
    assert data["next"] is not None
    assert data["previous"] is None

    # بررسی صفحه دوم
    response = client.get(
        "/products/api/v1/products/",
        {"page": 2},
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 15
    assert len(data["results"]) == 3
    assert data["next"] is None
    assert data["previous"] is not None


@pytest.mark.django_db
def test_anonymous_user_cannot_create_product(client):
    response = client.post(
        "/products/api/v1/products/",
        data={
            "name": "Unauthorized Product",
            "price": 1000000,
        },
        content_type="application/json",
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 405

    data = response.json()

    assert data["success"] is False
    assert data["error"]["code"] == "method_not_allowed"

@pytest.mark.django_db
def test_invalid_pagination_page_returns_404(client):
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

    response = client.get(
        "/products/api/v1/products/",
        {"page": 999},
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 404

    data = response.json()

    assert data["success"] is False
    assert data["error"]["code"] == "not_found"
    assert data["error"]["message"] == "Invalid page."



@pytest.mark.django_db
def test_nonexistent_product_returns_404(client):
    response = client.get(
        "/products/api/v1/products/999999/",
        HTTP_ACCEPT="application/json",
    )

    assert response.status_code == 404

    data = response.json()

    assert data["success"] is False
    assert data["error"]["code"] == "not_found"


@pytest.mark.django_db
def test_in_stock_filter_uses_variant_stock(client):
    category = Category.objects.create(
        name="Mobiles",
        slug="mobiles",
    )

    product = Product.objects.create(
        category=category,
        name="iPhone 16",
        slug="iphone-16",
        price=60_000_000,
        stock=0,
    )

    ProductVariant.objects.create(
        product=product,
        sku="IPHONE-16-BLACK-128",
        color="Black",
        storage="128GB",
        price=65_000_000,
        stock=5,
        is_active=True,
    )

    response = client.get(
        "/products/api/v1/products/",
        {"in_stock": "true"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["count"] == 1
    assert data["results"][0]["id"] == product.id
    assert data["results"][0]["is_available"] is True



@pytest.mark.django_db
def test_price_filter_uses_cheapest_available_variant(client):
    category = Category.objects.create(name="Mobiles", slug="mobiles-price")

    product = Product.objects.create(
        category=category,
        name="iPhone 16 Pro",
        slug="iphone-16-pro",
        price=40_000_000,
        stock=0,
    )

    ProductVariant.objects.create(
        product=product,
        sku="IP16-128",
        color="Black",
        storage="128GB",
        price=65_000_000,
        stock=3,
    )

    ProductVariant.objects.create(
        product=product,
        sku="IP16-256",
        color="Black",
        storage="256GB",
        price=75_000_000,
        stock=5,
    )

    response = client.get(
        "/products/api/v1/products/",
        {"min_price": 60_000_000, "max_price": 70_000_000},
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["results"][0]["id"] == product.id
    assert response.json()["results"][0]["effective_price"] == 65_000_000


@pytest.mark.django_db
def test_out_of_stock_variant_is_not_used_for_effective_price(client):
    category = Category.objects.create(name="Mobiles", slug="mobiles-stock")

    product = Product.objects.create(
        category=category,
        name="Galaxy S25",
        slug="galaxy-s25",
        price=30_000_000,
        stock=0,
    )

    ProductVariant.objects.create(
        product=product,
        sku="S25-CHEAP",
        color="Black",
        storage="128GB",
        price=40_000_000,
        stock=0,
    )

    ProductVariant.objects.create(
        product=product,
        sku="S25-AVAILABLE",
        color="Black",
        storage="256GB",
        price=55_000_000,
        stock=4,
    )

    response = client.get("/products/api/v1/products/")

    assert response.status_code == 200

    data = response.json()["results"][0]

    assert data["effective_price"] == 55_000_000
    assert data["default_variant"]["sku"] == "S25-AVAILABLE"
    assert data["is_available"] is True


@pytest.mark.django_db
def test_price_ordering_uses_effective_price(client):
    category = Category.objects.create(name="Mobiles", slug="mobiles-order")

    simple = Product.objects.create(
        category=category,
        name="Simple Phone",
        slug="simple-phone",
        price=50_000_000,
        stock=2,
    )

    variable = Product.objects.create(
        category=category,
        name="Variable Phone",
        slug="variable-phone",
        price=10_000_000,
        stock=0,
    )

    ProductVariant.objects.create(
        product=variable,
        sku="VARIABLE-128",
        color="Black",
        storage="128GB",
        price=70_000_000,
        stock=3,
    )

    response = client.get(
        "/products/api/v1/products/",
        {"ordering": "effective_price"},
    )

    assert response.status_code == 200

    results = response.json()["results"]

    assert [item["id"] for item in results] == [
        simple.id,
        variable.id,
    ]

    assert [item["effective_price"] for item in results] == [
        50_000_000,
        70_000_000,
    ]


@pytest.mark.django_db
def test_out_of_stock_filter_excludes_available_variants(client):
    category = Category.objects.create(name="Mobiles", slug="mobiles-unavailable")

    available = Product.objects.create(
        category=category,
        name="Available Phone",
        slug="available-phone",
        price=20_000_000,
        stock=0,
    )

    unavailable = Product.objects.create(
        category=category,
        name="Unavailable Phone",
        slug="unavailable-phone",
        price=30_000_000,
        stock=0,
    )

    ProductVariant.objects.create(
        product=available,
        sku="AVAILABLE-VARIANT",
        color="Black",
        storage="128GB",
        price=25_000_000,
        stock=2,
    )

    ProductVariant.objects.create(
        product=unavailable,
        sku="UNAVAILABLE-VARIANT",
        color="Black",
        storage="128GB",
        price=35_000_000,
        stock=0,
    )

    response = client.get(
        "/products/api/v1/products/",
        {"in_stock": "false"},
    )

    assert response.status_code == 200

    ids = [item["id"] for item in response.json()["results"]]

    assert unavailable.id in ids
    assert available.id not in ids


@pytest.mark.django_db
def test_draft_product_not_returned_by_catalog_filters(client):
    category = Category.objects.create(name="Mobiles", slug="mobiles-drafts")

    Product.objects.create(
        category=category,
        name="Draft Phone",
        slug="draft-phone",
        price=40_000_000,
        stock=5,
        status=Product.Status.DRAFT,
    )

    response = client.get(
        "/products/api/v1/products/",
        {
            "in_stock": "true",
            "min_price": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.django_db
def test_unavailable_variant_product_has_null_effective_price(client):
    category = Category.objects.create(name="Mobiles", slug="mobiles-null-price")

    product = Product.objects.create(
        category=category,
        name="Unavailable Galaxy",
        slug="unavailable-galaxy",
        price=30_000_000,
        stock=0,
    )

    ProductVariant.objects.create(
        product=product,
        sku="GALAXY-OUT",
        color="Black",
        storage="128GB",
        price=40_000_000,
        stock=0,
    )

    response = client.get("/products/api/v1/products/")

    assert response.status_code == 200

    item = response.json()["results"][0]

    assert item["effective_price"] is None
    assert item["default_variant"] is None
    assert item["is_available"] is False


@pytest.mark.django_db
def test_product_detail_contains_catalog_information(client):
    category = Category.objects.create(name="Mobiles", slug="mobiles-detail")

    product = Product.objects.create(
        category=category,
        name="iPhone 16",
        slug="iphone-16-detail",
        price=60_000_000,
        stock=3,
    )

    response = client.get(
        f"/products/api/v1/products/{product.pk}/",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == product.pk
    assert data["category"]["id"] == category.pk
    assert data["effective_price"] == 60_000_000
    assert data["is_available"] is True

    for field in [
        "images",
        "brand",
        "attribute_values",
        "variants",
        "default_variant",
    ]:
        assert field in data