import pytest

from products.models import Category, Product


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
        {"ordering": "price"},
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
        {"ordering": "-price"},
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