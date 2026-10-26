from django.conf import settings
from django.db import models


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name='shopping_cart')
    guest_digest = models.CharField(max_length=64, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(user__isnull=False, guest_digest__isnull=True) | models.Q(user__isnull=True, guest_digest__isnull=False)), name='cart_exactly_one_owner')]


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', null=True, on_delete=models.SET_NULL)
    variant = models.ForeignKey('products.ProductVariant', null=True, blank=True, on_delete=models.SET_NULL)
    selection_key = models.CharField(max_length=100)
    product_name = models.CharField(max_length=200)
    variant_name = models.CharField(max_length=210, blank=True)
    had_variant = models.BooleanField(default=False)
    quantity = models.PositiveIntegerField()
    price_seen = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['cart', 'selection_key'], name='cart_unique_selection'),
            models.CheckConstraint(condition=models.Q(quantity__gte=1, quantity__lte=99), name='cart_quantity_1_to_99'),
        ]


class CartOperation(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='operations')
    request_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['cart', 'request_id'], name='cart_unique_operation')]
