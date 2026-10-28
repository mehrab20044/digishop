import re

import django_filters
from django.db import models
from django.db.models import (
    BigIntegerField,
    Case,
    Exists,
    F,
    OuterRef,
    Subquery,
    When,
)
from rest_framework.exceptions import ValidationError

from products.models import Category, Product, ProductVariant
from products.services.category_query_service import (
    MAX_SELECTED_CATEGORIES,
    filter_category_branches,
)


class ProductFilter(django_filters.FilterSet):
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(),
        method="filter_category",
    )

    categories = django_filters.CharFilter(
        method="filter_categories",
        max_length=250,
    )

    min_price = django_filters.NumberFilter(
        method="filter_min_price",
    )

    max_price = django_filters.NumberFilter(
        method="filter_max_price",
    )

    in_stock = django_filters.BooleanFilter(
        method="filter_in_stock",
    )

    def filter_category(self, queryset, name, value):
        return filter_category_branches(
            queryset,
            [value.pk],
        )

    def filter_categories(self, queryset, name, value):
        parts = value.split(",")

        if len(parts) > MAX_SELECTED_CATEGORIES:
            raise ValidationError({
                "categories": (
                    f"انتخاب هم‌زمان حداکثر "
                    f"{MAX_SELECTED_CATEGORIES} دسته مجاز است."
                ),
            })

        category_ids = []

        for part in parts:
            token = part.strip()

            if (
                len(token) > 19
                or re.fullmatch(r"[1-9][0-9]*", token) is None
            ):
                raise ValidationError({
                    "categories": (
                        "شناسه‌های مثبت دسته‌ها را با کامای انگلیسی "
                        "جدا کنید؛ مانند 8,11."
                    ),
                })

            category_id = int(token)

            if category_id > 9223372036854775807:
                raise ValidationError({
                    "categories": "شناسهٔ دسته‌بندی معتبر نیست.",
                })

            category_ids.append(category_id)

        return filter_category_branches(
            queryset,
            category_ids,
        )

    def filter_in_stock(self, queryset, name, value):
        available_variants = ProductVariant.objects.filter(
            product_id=OuterRef("pk"),
            is_active=True,
            stock__gt=0,
            price__gt=0,
        )
        any_variants = ProductVariant.objects.filter(
            product_id=OuterRef("pk"),
        )

        queryset = queryset.annotate(
            _has_variants=Exists(any_variants),
            _has_available_variant=Exists(available_variants),
        )

        available = (
            models.Q(_has_available_variant=True)
            | models.Q(
                _has_variants=False,
                stock__gt=0,
                price__gt=0,
            )
        )

        if value:
            return queryset.filter(available)

        return queryset.exclude(available)

    def filter_min_price(self, queryset, name, value):
        queryset = self._with_effective_price(queryset)
        return queryset.filter(_effective_price__gte=value)

    def filter_max_price(self, queryset, name, value):
        queryset = self._with_effective_price(queryset)
        return queryset.filter(_effective_price__lte=value)

    @staticmethod
    def _with_effective_price(queryset):
        valid_variants = (
            ProductVariant.objects.filter(
                product_id=OuterRef("pk"),
                is_active=True,
                stock__gt=0,
                price__gt=0,
            )
            .order_by("price", "id")
        )

        any_variants = ProductVariant.objects.filter(
            product_id=OuterRef("pk"),
        )

        return queryset.annotate(
            _effective_price=Case(
                When(
                    Exists(any_variants),
                    then=Subquery(
                        valid_variants.values("price")[:1],
                    ),
                ),
                default=F("price"),
                output_field=BigIntegerField(),
            ),
        )

    class Meta:
        model = Product
        fields = [
            "category",
            "categories",
            "min_price",
            "max_price",
            "in_stock",
        ]