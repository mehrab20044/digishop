from products.models import Category, Product


class ProductService:
    @staticmethod
    def get_active_products():
        return (
            Product.objects.filter(is_active=True)
            .select_related("category")
            .prefetch_related("images")
            .order_by("-created_at")
        )

    @staticmethod
    def get_categories():
        return Category.objects.all().order_by("name")