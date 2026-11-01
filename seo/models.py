from django.conf import settings
from django.db import models


class SEOSettings(models.Model):
    allow_crawling = models.BooleanField(
        default=False,
        verbose_name="اجازه خزش عمومی ربات‌ها",
    )

    version = models.PositiveIntegerField(
        "نسخه تغییرات",
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
        verbose_name="تغییردهنده",
    )
    old_value = models.BooleanField("مقدار قبلی")
    new_value = models.BooleanField("مقدار جدید")
    changed_at = models.DateTimeField("زمان تغییر", auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "تاریخچه تغییر سئو"
        verbose_name_plural = "تاریخچه تغییرات سئو"

    def __str__(self):
        return f"{self.old_value} → {self.new_value}"


class PageSearchRule(models.Model):
    kind = models.CharField(max_length=16, choices=[(value, value) for value in ("home", "catalog", "directory", "product", "category", "page")])
    object_id = models.PositiveBigIntegerField(default=0)
    crawl = models.CharField(max_length=8, default="inherit", choices=[("inherit", "پیش‌فرض"), ("allow", "مجاز"), ("block", "مسدود")])
    indexing = models.CharField(max_length=8, default="inherit", choices=[("inherit", "پیش‌فرض"), ("index", "مجاز"), ("noindex", "غیرمجاز")])
    version = models.PositiveIntegerField(default=0, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kind", "object_id"], name="seo_unique_page_rule")]
        verbose_name = "قانون سئوی صفحه"
        verbose_name_plural = "قوانین سئوی صفحات"

    def __str__(self):
        return f"{self.kind}:{self.object_id}"


class RobotsDocument(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, serialize=False)
    draft = models.JSONField(default=dict)
    published = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    published_revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name="+", on_delete=models.SET_NULL)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(pk=1), name="seo_single_robots_document")]
        verbose_name = "سند robots.txt"
        verbose_name_plural = "اسناد robots.txt"
