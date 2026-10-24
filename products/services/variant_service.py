from products.models import ProductVariant


def get_default_variant(product):
    return (
        ProductVariant.objects.filter(
            product=product,
            is_active=True,
            stock__gt=0,
        )
        .order_by("price", "id")
        .first()
    )
def is_product_available(product):
    if not product.is_active:
        return False

    if product.variants.exists():
        return product.variants.filter(
            is_active=True,
            stock__gt=0,
        ).exists()

    return product.stock > 0