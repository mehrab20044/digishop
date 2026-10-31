from django.conf import settings
from django.db import models


class SavedProduct(models.Model):
    class Kind(models.TextChoices):
        FAVORITE = "favorite", "علاقه‌مندی"
        LATER = "later", "خرید بعدی"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_products",
    )
    product = models.ForeignKey("products.Product", on_delete=models.CASCADE)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product", "kind"], name="accounts_saved_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["favorite", "later"]),
                name="accounts_saved_kind_valid",
            ),
        ]
