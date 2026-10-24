from django.core.validators import FileExtensionValidator
from django.db import models

from .validators import (
    validate_product_image_content,
    validate_product_image_size,
)


class Category(models.Model):
    name = models.CharField("نام دسته‌بندی", max_length=100, unique=True)
    slug = models.SlugField(
        "نامک",
        max_length=120,
        unique=True,
        allow_unicode=True,
    )

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="دسته‌بندی",
    )

    name = models.CharField("نام محصول", max_length=200)
    slug = models.SlugField(
        "نامک",
        max_length=220,
        unique=True,
        allow_unicode=True,
    )
    description = models.TextField("توضیحات قدیمی", blank=True)
    short_description = models.CharField(
        "توضیح کوتاه",
        max_length=500,
        blank=True,
    )
    long_description = models.TextField("توضیحات کامل", blank=True)
    gallery_description = models.TextField("توضیحات گالری", blank=True)
    price = models.PositiveBigIntegerField("قیمت")
    stock = models.PositiveIntegerField("موجودی", default=0)
    image = models.ImageField(
        "تصویر قدیمی",
        upload_to="products/",
        blank=True,
    )

    is_active = models.BooleanField("فعال و قابل انتشار", default=True)
    created_at = models.DateTimeField("زمان ایجاد", auto_now_add=True)

    class Meta:
        verbose_name = "محصول"
        verbose_name_plural = "محصولات"

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="images",
        verbose_name="محصول",
    )
    image = models.ImageField(
        "فایل تصویر",
        upload_to="products/gallery/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=["jpg", "jpeg", "png", "webp"],
            ),
            validate_product_image_size,
            validate_product_image_content,
        ],
    )
    title = models.CharField("عنوان قدیمی", max_length=200, blank=True)
    alt_text = models.CharField("متن جایگزین قدیمی", max_length=250, blank=True)
    description = models.TextField("توضیح قدیمی", blank=True)
    caption = models.CharField("زیرنویس قدیمی", max_length=500, blank=True)
    sort_order = models.PositiveIntegerField("ترتیب نمایش", default=0)
    is_primary = models.BooleanField("تصویر اصلی", default=False)
    created_at = models.DateTimeField("زمان ایجاد", auto_now_add=True)
    updated_at = models.DateTimeField("آخرین تغییر", auto_now=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "تصویر محصول"
        verbose_name_plural = "تصاویر محصولات"
        constraints = [
            models.UniqueConstraint(
                fields=["product"],
                condition=models.Q(is_primary=True),
                name="unique_primary_image_per_product",
            )
        ]
