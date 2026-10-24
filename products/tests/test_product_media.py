from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from products.admin import ProductImageAdminForm
from products.models import Category, Product, ProductImage
from products.services.image_service import prepare_product_image
from products.validators import (
    MAX_PRODUCT_IMAGE_SIZE,
    validate_product_image_content,
    validate_product_image_size,
)

pytestmark = pytest.mark.django_db


def image_bytes(
    *,
    image_format="PNG",
    size=(20, 10),
    mode="RGB",
    color=None,
    exif=None,
):
    output = BytesIO()
    color = color or ((255, 0, 0, 128) if mode == "RGBA" else "red")
    image = Image.new(mode, size, color)
    save_options = {"exif": exif} if exif is not None else {}
    image.save(output, format=image_format, **save_options)
    return output.getvalue()


def upload(name="photo.png", **kwargs):
    return SimpleUploadedFile(
        name,
        image_bytes(**kwargs),
        content_type="image/png",
    )


@pytest.fixture
def product():
    category = Category.objects.create(name="Media", slug="media")
    return Product.objects.create(
        category=category,
        name="Media product",
        slug="media-product",
        price=100,
        is_active=False,
    )


@pytest.mark.parametrize(
    ("name", "image_format"),
    [("photo.jpg", "JPEG"), ("photo.png", "PNG"), ("photo.webp", "WEBP")],
)
def test_content_validator_accepts_supported_images(name, image_format):
    validate_product_image_content(upload(name, image_format=image_format))


def test_model_form_rejects_mismatched_extension(product):
    form = ProductImageAdminForm(
        data={"product": product.pk, "sort_order": 0},
        files={"image": upload("photo.gif")},
    )

    assert not form.is_valid()
    assert "image" in form.errors


def test_content_validator_rejects_disguised_and_corrupt_images():
    disguised = SimpleUploadedFile("fake.jpg", b"not an image")

    with pytest.raises(ValidationError, match="نامعتبر یا خراب"):
        validate_product_image_content(disguised)


def test_size_validator_accepts_limit_and_rejects_above_it():
    validate_product_image_size(ContentFile(b"x" * MAX_PRODUCT_IMAGE_SIZE))

    with pytest.raises(ValidationError, match="۵ مگابایت"):
        validate_product_image_size(
            ContentFile(b"x" * (MAX_PRODUCT_IMAGE_SIZE + 1))
        )


def test_content_validator_rejects_excessive_dimensions(monkeypatch):
    monkeypatch.setattr(
        "products.validators.MAX_PRODUCT_IMAGE_PIXELS", 100
    )

    with pytest.raises(ValidationError, match="۲۰ میلیون پیکسل"):
        validate_product_image_content(upload(size=(11, 10)))


def test_content_validator_handles_decompression_bomb(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)

    with pytest.raises(ValidationError, match="بیش از حد مجاز"):
        validate_product_image_content(upload(size=(20, 20)))


def test_prepare_image_outputs_webp_without_upscaling_or_metadata():
    source = upload(size=(30, 15))
    prepared = prepare_product_image(source)

    assert prepared.name.endswith(".webp")
    with Image.open(prepared) as result:
        assert result.format == "WEBP"
        assert result.size == (30, 15)
        assert not result.getexif()


def test_prepare_image_resizes_large_image_and_preserves_transparency():
    prepared = prepare_product_image(
        upload(size=(2000, 1000), mode="RGBA")
    )

    with Image.open(prepared) as result:
        assert result.size == (1600, 800)
        assert result.mode == "RGBA"
        assert result.getpixel((0, 0))[3] < 255


def test_prepare_image_applies_exif_orientation_and_removes_exif():
    exif = Image.Exif()
    exif[274] = 6
    source = upload(
        "oriented.jpg",
        image_format="JPEG",
        size=(40, 20),
        exif=exif,
    )
    prepared = prepare_product_image(source)

    with Image.open(prepared) as result:
        assert result.size == (20, 40)
        assert not result.getexif()


def admin_add_payload(product):
    return {
        "category": str(product.category_id),
        "name": product.name,
        "slug": product.slug,
        "short_description": "",
        "long_description": "",
        "price": str(product.price),
        "stock": "0",
        "images-TOTAL_FORMS": "1",
        "images-INITIAL_FORMS": "0",
        "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "1000",
        "images-0-product": str(product.pk),
        "images-0-image": upload(size=(50, 25)),
        "images-0-title": "Uploaded",
        "images-0-alt_text": "Uploaded image",
        "images-0-description": "",
        "images-0-caption": "",
        "images-0-sort_order": "0",
        "images-0-is_primary": "on",
        "_save": "Save",
        "attribute_values-TOTAL_FORMS": "0",
        "attribute_values-INITIAL_FORMS": "0",
        "attribute_values-MIN_NUM_FORMS": "0",
        "attribute_values-MAX_NUM_FORMS": "1000",
        "variants-TOTAL_FORMS": "0",
        "variants-INITIAL_FORMS": "0",
        "variants-MIN_NUM_FORMS": "0",
        "variants-MAX_NUM_FORMS": "1000",
        "status": product.status,
    }


def admin_bulk_payload(product, images):
    return {
        "category": str(product.category_id),
        "name": product.name,
        "slug": product.slug,
        "short_description": "Short product text",
        "long_description": "Long product text",
        "gallery_description": "One description for the whole gallery",
        "price": str(product.price),
        "stock": "10",
        "is_active": "on",
        "gallery_images": images,
        "images-TOTAL_FORMS": "0",
        "images-INITIAL_FORMS": "0",
        "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "1000",
        "_save": "Save",
        "attribute_values-TOTAL_FORMS": "0",
        "attribute_values-INITIAL_FORMS": "0",
        "attribute_values-MIN_NUM_FORMS": "0",
        "attribute_values-MAX_NUM_FORMS": "1000",
        "variants-TOTAL_FORMS": "0",
        "variants-INITIAL_FORMS": "0",
        "variants-MIN_NUM_FORMS": "0",
        "variants-MAX_NUM_FORMS": "1000",
        "status": product.status,
    }


def test_admin_uploads_multiple_gallery_images_at_once(
    admin_client, product, tmp_path
):
    images = [
        upload(f"gallery-{index}.png", size=(30 + index, 20))
        for index in range(3)
    ]

    with override_settings(MEDIA_ROOT=tmp_path):
        response = admin_client.post(
            reverse("admin:products_product_change", args=[product.pk]),
            admin_bulk_payload(product, images),
        )

        assert response.status_code == 302
        product.refresh_from_db()
        gallery = list(product.images.all())
        assert product.gallery_description == (
            "One description for the whole gallery"
        )
        assert len(gallery) == 3
        assert sum(image.is_primary for image in gallery) == 1
        assert gallery[0].is_primary is True
        assert all(image.image.name.endswith(".webp") for image in gallery)
        assert all(not image.title for image in gallery)
        assert all(not image.description for image in gallery)


def test_admin_upload_uses_image_processing(admin_client, product, tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        response = admin_client.post(
            reverse("admin:products_product_change", args=[product.pk]),
            admin_add_payload(product),
        )

        assert response.status_code == 302
        stored = product.images.get()
        assert stored.image.name.endswith(".webp")
        with stored.image.open("rb") as saved:
            with Image.open(saved) as result:
                assert result.format == "WEBP"


def test_metadata_edit_does_not_reprocess_existing_image(product, tmp_path):
    with override_settings(MEDIA_ROOT=tmp_path):
        item = ProductImage.objects.create(
            product=product,
            image=ContentFile(image_bytes(), name="existing.png"),
            title="Before",
            is_primary=True,
        )
        form = ProductImageAdminForm(
            data={
                "product": product.pk,
                "title": "After",
                "sort_order": 0,
                "is_primary": True,
            },
            instance=item,
        )

        with patch("products.admin.prepare_product_image") as processor:
            assert form.is_valid(), form.errors
            saved = form.save()

        processor.assert_not_called()
        assert saved.image.name == item.image.name


def test_replacing_image_deletes_old_file_after_commit(
    product, tmp_path, django_capture_on_commit_callbacks
):
    with override_settings(MEDIA_ROOT=tmp_path):
        item = ProductImage.objects.create(
            product=product,
            image=ContentFile(image_bytes(), name="old.png"),
        )
        storage = item.image.storage
        old_name = item.image.name

        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            item.image = ContentFile(image_bytes(), name="new.png")
            item.save()
            assert storage.exists(old_name)

        assert len(callbacks) == 1
        callbacks[0]()
        assert not storage.exists(old_name)
        assert storage.exists(item.image.name)


def test_deleting_image_waits_for_commit(
    product, tmp_path, django_capture_on_commit_callbacks
):
    with override_settings(MEDIA_ROOT=tmp_path):
        item = ProductImage.objects.create(
            product=product,
            image=ContentFile(image_bytes(), name="delete.png"),
        )
        storage = item.image.storage
        name = item.image.name

        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            item.delete()
            assert storage.exists(name)

        assert len(callbacks) == 1
        callbacks[0]()
        assert not storage.exists(name)


def test_rolled_back_delete_keeps_file(
    product, tmp_path, django_capture_on_commit_callbacks
):
    with override_settings(MEDIA_ROOT=tmp_path):
        item = ProductImage.objects.create(
            product=product,
            image=ContentFile(image_bytes(), name="rollback-delete.png"),
        )
        storage = item.image.storage
        name = item.image.name

        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            item.delete()

        assert callbacks
        assert storage.exists(name)


def test_rollback_does_not_delete_previous_file(
    product, tmp_path, django_capture_on_commit_callbacks
):
    with override_settings(MEDIA_ROOT=tmp_path):
        item = ProductImage.objects.create(
            product=product,
            image=ContentFile(image_bytes(), name="old.png"),
        )
        storage = item.image.storage
        old_name = item.image.name

        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            item.image = ContentFile(image_bytes(), name="new.png")
            item.save()

        assert callbacks
        assert storage.exists(old_name)


def test_shared_legacy_reference_prevents_file_deletion(
    product, tmp_path, django_capture_on_commit_callbacks
):
    with override_settings(MEDIA_ROOT=tmp_path):
        shared = ContentFile(image_bytes(), name="shared.png")
        item = ProductImage.objects.create(product=product, image=shared)
        product.image = item.image.name
        product.save()
        name = item.image.name
        storage = item.image.storage

        with django_capture_on_commit_callbacks(execute=True):
            item.delete()

        assert storage.exists(name)


def test_deleting_product_removes_its_unreferenced_files(
    product, tmp_path, django_capture_on_commit_callbacks
):
    with override_settings(MEDIA_ROOT=tmp_path):
        item = ProductImage.objects.create(
            product=product,
            image=ContentFile(image_bytes(), name="gallery.png"),
        )
        storage = item.image.storage
        name = item.image.name

        with django_capture_on_commit_callbacks(execute=True):
            product.delete()

        assert not storage.exists(name)
