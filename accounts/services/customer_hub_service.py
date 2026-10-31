from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError

from accounts.models import SavedProduct
from products.models import Product


@transaction.atomic
def save_product(user, product_id, kind, enabled):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    if kind not in SavedProduct.Kind.values or type(enabled) is not bool:
        raise ValidationError("انتخاب فهرست معتبر نیست.")
    if not enabled:
        SavedProduct.objects.filter(
            user=user, product_id=product_id, kind=kind
        ).delete()
        return
    product = get_object_or_404(
        Product.objects.filter(is_active=True, status=Product.Status.PUBLISHED),
        pk=product_id,
    )
    SavedProduct.objects.get_or_create(user=user, product=product, kind=kind)
