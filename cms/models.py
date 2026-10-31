import uuid

from django.conf import settings
from django.db import models


class Page(models.Model):
    title = models.CharField("عنوان صفحه", max_length=160)
    slug = models.SlugField("نامک", max_length=120, allow_unicode=True, unique=True)
    seo_title = models.CharField(max_length=180, blank=True)
    seo_description = models.CharField(max_length=320, blank=True)
    layout = models.CharField(max_length=20, default="simple")
    footer_visible = models.BooleanField(default=True)
    footer_label = models.CharField(max_length=80, blank=True)
    footer_order = models.PositiveIntegerField(default=0)
    blocks = models.JSONField(default=list)
    published = models.JSONField(default=dict, editable=False)
    is_published = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, editable=False
    )

    class Meta:
        ordering = ["-updated_at", "-pk"]
        permissions = [("publish_page", "Can publish or hide pages")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(revision__gte=1), name="cms_page_revision_positive"
            )
        ]

    def __str__(self):
        return self.title


class PageImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.ImageField(upload_to="cms/images/%Y/%m/")
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )

    class Meta:
        ordering = ["-created_at"]


class SiteTheme(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    draft = models.JSONField(default=dict)
    published = models.JSONField(default=dict)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )

    class Meta:
        permissions = [("publish_sitetheme", "Can publish store appearance")]
        constraints = [
            models.CheckConstraint(condition=models.Q(pk=1), name="cms_theme_singleton")
        ]


class BannerSet(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    draft = models.JSONField(default=list)
    published = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        permissions = [("publish_bannerset", "Can publish store banners")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pk=1), name="cms_banners_singleton"
            )
        ]


class BannerVideo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to="cms/videos/%Y/%m/")
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    duration = models.FloatField()
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["-created_at"]


from .footer_models import SiteFooter  # noqa: E402,F401
