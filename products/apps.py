from django.apps import AppConfig


class ProductsConfig(AppConfig):
    name = "products"
    verbose_name = "محصولات و دسته‌بندی‌ها"

    def ready(self):
        from . import signals  # noqa: F401
