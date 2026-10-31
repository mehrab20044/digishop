from products.models import Product, ProductVariant


def get_default_variant(product):
    if (
        not product.is_active
        or product.status != Product.Status.PUBLISHED
    ):
        return None

    return (
        ProductVariant.objects.filter(
            product=product,
            is_active=True,
            stock__gt=0,
            price__gt=0,
        )
        .select_related("product")
        .order_by("price", "id")
        .first()
    )
def is_product_available(product):
    if (
        not product.is_active
        or product.status != Product.Status.PUBLISHED
    ):
        return False

    if product.variants.exists():
        return product.variants.filter(
            is_active=True,
            stock__gt=0,
            price__gt=0,
        ).exists()

    return product.stock > 0 and product.price > 0