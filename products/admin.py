from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.models import BaseInlineFormSet

from .models import Category, Product, ProductImage


class ProductImageAdminForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = "__all__"

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        exclude.add("is_primary")
        return exclude


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

        if self.instance.is_active and primary_count != 1:
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


class ProductImageInline(admin.StackedInline):
    model = ProductImage
    form = ProductImageAdminForm
    formset = ProductImageInlineFormSet
    extra = 1
    fields = (
        "image",
        "title",
        "alt_text",
        "description",
        "caption",
        "sort_order",
        "is_primary",
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price",
        "stock",
        "is_active",
    )
    ordering = ("-created_at",)
    list_filter = ("category", "is_active")
    search_fields = ("name", "slug", "category__name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline]
    exclude = ("description", "image")