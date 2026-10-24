from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Product, ProductImage


def _is_referenced(name, *, using):
    if not name:
        return False

    return (
        Product.objects.using(using).filter(image=name).exists()
        or ProductImage.objects.using(using).filter(image=name).exists()
    )


def _delete_if_unreferenced(*, name, storage, using):
    def delete_file():
        if not _is_referenced(name, using=using) and storage.exists(name):
            storage.delete(name)

    transaction.on_commit(delete_file, using=using)


def _remember_previous_file(instance, model, *, using):
    if not instance.pk:
        instance._previous_image_name = ""
        return

    previous = (
        model.objects.using(using)
        .filter(pk=instance.pk)
        .values_list("image", flat=True)
        .first()
    )
    instance._previous_image_name = previous or ""


@receiver(pre_save, sender=ProductImage)
@receiver(pre_save, sender=Product)
def remember_previous_image(sender, instance, using, **kwargs):
    _remember_previous_file(instance, sender, using=using)


@receiver(post_save, sender=ProductImage)
@receiver(post_save, sender=Product)
def delete_replaced_image(sender, instance, using, **kwargs):
    old_name = getattr(instance, "_previous_image_name", "")
    new_name = instance.image.name if instance.image else ""
    if old_name and old_name != new_name:
        _delete_if_unreferenced(
            name=old_name,
            storage=instance.image.storage,
            using=using,
        )


@receiver(post_delete, sender=ProductImage)
@receiver(post_delete, sender=Product)
def delete_removed_image(sender, instance, using, **kwargs):
    if instance.image:
        _delete_if_unreferenced(
            name=instance.image.name,
            storage=instance.image.storage,
            using=using,
        )
