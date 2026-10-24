import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from products.models import Category, Product, ProductImage
from products.services.product_service import ProductService


pytestmark = pytest.mark.django_db


@pytest.fixture
def product():
    category = Category.objects.create(name="Phones", slug="phones")
    return Product.objects.create(
        category=category,
        name="Test Phone",
        slug="test-phone",
        price=1000000,
        short_description="Short text",
        long_description="Full description",
        is_active=True,
    )


def add_image(product, *, primary=False, order=0):
    return ProductImage.objects.create(
        product=product,
        image=f"products/gallery/photo-{order}.jpg",
        title="Product photo",
        alt_text="Front view",
        description="Image description",
        caption="Image caption",
        sort_order=order,
        is_primary=primary,
    )


def admin_payload(product, rows, *, active=True):
    data = {
        "category": str(product.category_id),
        "name": product.name,
        "slug": product.slug,
        "short_description": product.short_description,
        "long_description": product.long_description,
        "price": str(product.price),
        "stock": str(product.stock),
        "images-TOTAL_FORMS": str(len(rows)),
        "images-INITIAL_FORMS": str(len(rows)),
        "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "1000",
        "_save": "Save",
    }

    if active:
        data["is_active"] = "on"

    for index, (image, primary, delete) in enumerate(rows):
        prefix = f"images-{index}"
        data.update({
            f"{prefix}-id": str(image.pk),
            f"{prefix}-product": str(product.pk),
            f"{prefix}-title": image.title,
            f"{prefix}-alt_text": image.alt_text,
            f"{prefix}-description": image.description,
            f"{prefix}-caption": image.caption,
            f"{prefix}-sort_order": str(image.sort_order),
        })

        if primary:
            data[f"{prefix}-is_primary"] = "on"
        if delete:
            data[f"{prefix}-DELETE"] = "on"

    return data


def test_database_rejects_two_primary_images(product):
    add_image(product, primary=True)

    with pytest.raises(IntegrityError), transaction.atomic():
        add_image(product, primary=True, order=1)

    assert product.images.filter(is_primary=True).count() == 1


def test_gallery_allows_multiple_secondary_images(product):
    add_image(product, primary=True)
    add_image(product, order=1)
    add_image(product, order=2)

    assert product.images.count() == 3


def test_primary_images_are_independent_between_products(product):
    other = Product.objects.create(
        category=product.category,
        name="Other Phone",
        slug="other-phone",
        price=2000000,
    )

    add_image(product, primary=True)
    add_image(other, primary=True)

    assert ProductImage.objects.filter(is_primary=True).count() == 2


@pytest.mark.parametrize("endpoint", ["list", "detail"])
def test_api_returns_descriptions_and_ordered_gallery(
    client, product, endpoint
):
    later = add_image(product, order=5)
    first = add_image(product, primary=True, order=0)
    tied = add_image(product, order=5)

    url = "/products/api/v1/products/"
    if endpoint == "detail":
        url += f"{product.pk}/"

    response = client.get(url, HTTP_ACCEPT="application/json")
    assert response.status_code == 200

    body = response.json()
    data = body["results"][0] if endpoint == "list" else body

    assert data["short_description"] == "Short text"
    assert data["long_description"] == "Full description"
    assert [image["id"] for image in data["images"]] == [
        first.pk,
        later.pk,
        tied.pk,
    ]

    image = data["images"][0]
    assert image["image"].endswith(first.image.name)
    assert image["title"] == first.title
    assert image["alt_text"] == first.alt_text
    assert image["description"] == first.description
    assert image["caption"] == first.caption
    assert image["sort_order"] == 0
    assert image["is_primary"] is True
    assert image["created_at"]
    assert image["updated_at"]


def test_gallery_is_prefetched(product, django_assert_num_queries):
    add_image(product, primary=True)

    other = Product.objects.create(
        category=product.category,
        name="Other Phone",
        slug="other-phone",
        price=2000000,
    )
    add_image(other, primary=True)

    # One query for products/category, one for all images.
    with django_assert_num_queries(2):
        products = list(ProductService.get_active_products())
        galleries = [list(item.images.all()) for item in products]
        categories = [item.category.name for item in products]

    assert len(galleries) == 2
    assert all(len(gallery) == 1 for gallery in galleries)
    assert categories == ["Phones", "Phones"]


@pytest.mark.parametrize("active", [True, False])
def test_admin_requires_primary_image_only_when_active(
    admin_client, product, active
):
    url = reverse("admin:products_product_change", args=[product.pk])
    response = admin_client.post(
        url, admin_payload(product, [], active=active)
    )

    assert response.status_code == (200 if active else 302)

    if active:
        formset = response.context["inline_admin_formsets"][0].formset
        assert (
            "برای انتشار محصول، یک تصویر اصلی مشخص کنید."
            in formset.non_form_errors()
        )
    else:
        product.refresh_from_db()
        assert product.is_active is False


def test_admin_accepts_active_product_with_primary_image(
    admin_client, product
):
    primary = add_image(product, primary=True)
    url = reverse("admin:products_product_change", args=[product.pk])

    response = admin_client.post(
        url, admin_payload(product, [(primary, True, False)])
    )

    assert response.status_code == 302
    primary.refresh_from_db()
    assert primary.is_primary is True


@pytest.mark.parametrize("action", ["delete", "unmark"])
def test_admin_rejects_removing_only_primary_image(
    admin_client, product, action
):
    primary = add_image(product, primary=True)
    url = reverse("admin:products_product_change", args=[product.pk])
    rows = [(primary, action == "delete", action == "delete")]

    response = admin_client.post(url, admin_payload(product, rows))

    assert response.status_code == 200
    formset = response.context["inline_admin_formsets"][0].formset
    assert (
        "برای انتشار محصول، یک تصویر اصلی مشخص کنید."
        in formset.non_form_errors()
    )
    primary.refresh_from_db()
    assert primary.is_primary is True


@pytest.mark.parametrize("replacement_first", [True, False])
def test_admin_can_switch_primary_image(
    admin_client, product, replacement_first
):
    old = add_image(
        product, primary=True, order=1 if replacement_first else 0
    )
    replacement = add_image(
        product, order=0 if replacement_first else 1
    )
    images = list(product.images.all())
    rows = [
        (image, image.pk == replacement.pk, False)
        for image in images
    ]
    url = reverse("admin:products_product_change", args=[product.pk])

    response = admin_client.post(url, admin_payload(product, rows))

    if response.status_code == 200:
        formset = response.context["inline_admin_formsets"][0].formset
        pytest.fail(
            f"Product errors: "
            f"{response.context['adminform'].form.errors.as_json()}\n"
            f"Image errors: {formset.errors}\n"
            f"Gallery errors: {list(formset.non_form_errors())}"
        )

        assert response.status_code == 302
    old.refresh_from_db()
    replacement.refresh_from_db()
    assert old.is_primary is False
    assert replacement.is_primary is True



@pytest.mark.django_db(transaction=True)
def test_migrations_preserve_existing_descriptions_and_images():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    latest_targets = executor.loader.graph.leaf_nodes()
    old_target = [("products", "0001_initial")]

    try:
        executor.migrate(old_target)
        old_apps = executor.loader.project_state(old_target).apps
        OldCategory = old_apps.get_model("products", "Category")
        OldProduct = old_apps.get_model("products", "Product")

        category = OldCategory.objects.create(
            name="Legacy", slug="legacy"
        )
        original = OldProduct.objects.create(
            category=category,
            name="Legacy Phone",
            slug="legacy-phone",
            price=1000000,
            description="Existing description",
            image="products/original.jpg",
        )
        without_image = OldProduct.objects.create(
            category=category,
            name="No Image",
            slug="no-image",
            price=1000000,
            image="",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(latest_targets)

        migrated = Product.objects.get(pk=original.pk)
        assert migrated.description == "Existing description"
        assert migrated.long_description == "Existing description"
        assert migrated.short_description == ""
        assert migrated.image.name == "products/original.jpg"

        image = migrated.images.get()
        assert image.image.name == "products/original.jpg"
        assert image.is_primary is True
        assert image.title == migrated.name
        assert image.alt_text == migrated.name
        assert not ProductImage.objects.filter(
            product_id=without_image.pk
        ).exists()
    finally:
        MigrationExecutor(connection).migrate(latest_targets)