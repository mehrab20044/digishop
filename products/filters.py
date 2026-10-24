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

from products.models import Product, ProductVariant


class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(
        method="filter_min_price",
    )

    max_price = django_filters.NumberFilter(
        method="filter_max_price",
    )

    in_stock = django_filters.BooleanFilter(
        field_name="stock",
        lookup_expr="gt",
        method="filter_in_stock",
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
                    then=Subquery(valid_variants.values("price")[:1]),
                ),
                default=F("price"),
                output_field=BigIntegerField(),
            )
        )

    class Meta:
        model = Product
        fields = ["category", "min_price", "max_price", "in_stock"]
