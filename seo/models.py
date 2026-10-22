from django.conf import settings
from django.db import models


class SEOSettings(models.Model):
    allow_crawling = models.BooleanField(
        default=False,
        verbose_name="اجازه خزش عمومی ربات‌ها",
    )

    version = models.PositiveIntegerField(
        default=1,
        editable=False,
    )

    class Meta:
        verbose_name = "تنظیمات سئو"
        verbose_name_plural = "تنظیمات سئو"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SEOSettingsLog(models.Model):
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    old_value = models.BooleanField()
    new_value = models.BooleanField()
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "تاریخچه تغییر سئو"
        verbose_name_plural = "تاریخچه تغییرات سئو"

    def __str__(self):
        return f"{self.old_value} → {self.new_value}"
