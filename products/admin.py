from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.core.validators import FileExtensionValidator
from django.db import transaction
from django.db.models import Max
from django.forms.models import BaseInlineFormSet
from django.utils.html import format_html

from .models import (
    Attribute,
    Brand,
    Category,
    CategoryAttribute,
    Product,
    ProductAttributeValue,
    ProductImage,
    ProductVariant,
)
from .services.image_service import prepare_product_image
from .validators import (
    validate_product_image_content,
    validate_product_image_size,
)

validate_product_image_extension = FileExtensionValidator(
    allowed_extensions=["jpg", "jpeg", "png", "webp"]
)


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        if not files or files == [None]:
            return []

        prepared_images = []
        errors = []
        for image in files:
            try:
                cleaned = super().clean(image, initial)
                validate_product_image_extension(cleaned)
                validate_product_image_size(cleaned)
                validate_product_image_content(cleaned)
                prepared_images.append(prepare_product_image(cleaned))
            except ValidationError as exc:
                errors.extend(exc.error_list)
            except (OSError, SyntaxError, ValueError):
                errors.append(
                    ValidationError(
                        "پردازش یکی از تصاویر ممکن نیست.",
                        code="image_processing_failed",
                    )
                )

        if errors:
            raise ValidationError(errors)
        return prepared_images


class ProductAdminForm(forms.ModelForm):
    gallery_images = MultipleImageField(
        required=False,
        widget=MultipleImageInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        label="افزودن چند تصویر به گالری",
        help_text="همه تصاویر را هم‌زمان انتخاب کنید. اولین تصویر، تصویر اصلی می‌شود.",
    )

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("category")

        if not category or not self.instance.pk:
            return cleaned_data

        invalid = self.instance.attribute_values.exclude(
            attribute__category_attributes__category=category
        ).exists()

        if invalid:
            raise ValidationError(
                "این محصول مشخصاتی دارد که برای دسته‌بندی انتخاب‌شده مجاز نیستند."
            )

        status = cleaned_data.get("status")

        if status == Product.Status.PUBLISHED and self.instance.pk:
            invalid_variants = self.instance.variants.filter(price=0).exists()

            if invalid_variants:
                raise ValidationError(
                    "برای انتشار محصول، قیمت تمام تنوع‌های آن باید معتبر باشد."
                )

        return cleaned_data

    class Meta:
        model = Product
        fields = "__all__"


class ProductImageAdminForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = "__all__"

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        exclude.add("is_primary")
        if self.instance.pk and "image" not in self.changed_data:
            exclude.add("image")
        return exclude

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image

        # An unchanged FieldFile represents an existing image. Processing it
        # again would create a duplicate whenever only metadata is edited.
        if not isinstance(image, UploadedFile):
            return image

        # Validate the original upload before converting it. The validators
        # attached to the model will subsequently validate the WebP output.
        validate_product_image_extension(image)
        validate_product_image_size(image)
        validate_product_image_content(image)

        try:
            return prepare_product_image(image)
        except (OSError, SyntaxError, ValueError) as exc:
            raise ValidationError(
                "پردازش فایل تصویر ممکن نیست.",
                code="image_processing_failed",
            ) from exc


class ProductImageInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        if any(self.errors):
            return

        primary_count = 0

        for form in self.forms:
            data = form.cleaned_data

            if not data or data.get("DELETE"):
                continue

            if data.get("image") and data.get("is_primary"):
                primary_count += 1

        if primary_count > 1:
            raise ValidationError(
                "هر محصول حداکثر یک تصویر اصلی می‌تواند داشته باشد."
            )

        if hasattr(self.files, "getlist"):
            new_gallery_images = self.files.getlist("gallery_images")
        else:
            new_gallery_images = self.files.get("gallery_images", [])
        has_new_gallery_images = bool(new_gallery_images)
        if (
            self.instance.is_active
            and primary_count != 1
            and not (primary_count == 0 and has_new_gallery_images)
        ):
            raise ValidationError(
                "برای انتشار محصول، یک تصویر اصلی مشخص کنید."
            )

    def save(self, commit=True):
        if not commit:
            return super().save(commit=False)

        demoted_ids = [
            form.instance.pk
            for form in self.forms
            if form.instance.pk
            and form.cleaned_data
            and (
                form.cleaned_data.get("DELETE")
                or not form.cleaned_data.get("is_primary")
            )
        ]

        db_alias = self.instance._state.db

        with transaction.atomic(using=db_alias):
            ProductImage.objects.using(db_alias).filter(
                product_id=self.instance.pk,
                pk__in=demoted_ids,
                is_primary=True,
            ).update(is_primary=False)

            return super().save(commit=True)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    form = ProductImageAdminForm
    formset = ProductImageInlineFormSet
    extra = 0
    fields = (
        "thumbnail",
        "image",
        "sort_order",
        "is_primary",
    )
    readonly_fields = ("thumbnail",)

    @admin.display(description="پیش‌نمایش")
    def thumbnail(self, obj):
        if not obj or not obj.image:
            return "—"
        return format_html(
            '<img src="{}" width="90" height="90" '
            'style="object-fit:cover;border-radius:8px" alt="">',
            obj.image.url,
        )

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class CategoryAttributeInline(admin.TabularInline):
    model = CategoryAttribute
    extra = 1


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [CategoryAttributeInline]



class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1

    fields = (
        "sku",
        "color",
        "storage",
        "price",
        "stock",
        "is_active",
    )


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = (
        "name",
        "brand",
        "category",
        "price",
        "stock",
        "status",
        "is_active",
    )
    ordering = ("-created_at",)
    list_filter = ("category", "status","is_active")
    search_fields = ("name", "slug", "category__name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [
    ProductImageInline,
    ProductAttributeValueInline,
    ProductVariantInline,
]
    exclude = ("description", "image")

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        images = form.cleaned_data.get("gallery_images") or []
        if not images:
            return

        product = form.instance
        next_order = (
            product.images.aggregate(max_order=Max("sort_order"))["max_order"]
            or 0
        )
        has_primary = product.images.filter(is_primary=True).exists()

        for offset, image in enumerate(images, start=1):
            ProductImage.objects.create(
                product=product,
                image=image,
                sort_order=next_order + offset,
                is_primary=not has_primary and offset == 1,
            )

