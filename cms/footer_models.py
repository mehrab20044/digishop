from django.db import models


class SiteFooter(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    config = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "فوتر فروشگاه"
        verbose_name_plural = "فوتر فروشگاه"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pk=1), name="cms_footer_singleton"
            )
        ]
