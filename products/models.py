from django.core.exceptions import ValidationError
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




class Brand(models.Model):
    name = models.CharField("نام برند", max_length=150, unique=True)
    slug = models.SlugField(
        "نامک",
        max_length=170,
        unique=True,
        allow_unicode=True,
    )

    class Meta:
        verbose_name = "برند"
        verbose_name_plural = "برندها"
        ordering = ["name"]

    def __str__(self):
        return self.name



class Attribute(models.Model):
    name = models.CharField("نام ویژگی", max_length=100, unique=True)
    slug = models.SlugField(
        "نامک",
        max_length=120,
        unique=True,
        allow_unicode=True,
    )

    class Meta:
        verbose_name = "ویژگی"
        verbose_name_plural = "ویژگی‌ها"

    def __str__(self):
        return self.name


class CategoryAttribute(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="category_attributes",
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.PROTECT,
        related_name="category_attributes",
    )

    class Meta:
        verbose_name = "ویژگی دسته‌بندی"
        verbose_name_plural = "ویژگی‌های دسته‌بندی"
        constraints = [
            models.UniqueConstraint(
                fields=["category", "attribute"],
                name="unique_category_attribute",
            )
        ]

    def __str__(self):
        return f"{self.category} - {self.attribute}"


class ProductAttributeValue(models.Model):
    product = models.ForeignKey(
        "Product",
        on_delete=models.CASCADE,
        related_name="attribute_values",
        verbose_name="محصول",
    )
    attribute = models.ForeignKey(
        Attribute,
        on_delete=models.PROTECT,
        related_name="product_values",
        verbose_name="ویژگی",
    )
    value = models.CharField("مقدار ویژگی", max_length=255)

    def clean(self):
        super().clean()

        if not self.product_id or not self.attribute_id:
            return

        allowed = CategoryAttribute.objects.filter(
            category_id=self.product.category_id,
            attribute_id=self.attribute_id,
        ).exists()

        if not allowed:
            raise ValidationError({
                "attribute": "این ویژگی برای دسته‌بندی محصول تعریف نشده است."
        })

    class Meta:
        verbose_name = "مشخصه محصول"
        verbose_name_plural = "مشخصات محصولات"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "attribute"],
                name="unique_product_attribute",
            )
        ]

    def __str__(self):
        return f"{self.product} - {self.attribute}: {self.value}"



class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="دسته‌بندی",
    )

    name = models.CharField("نام محصول", max_length=200)
    brand = models.ForeignKey(
        Brand,
        on_delete=models.PROTECT,
        related_name="products",
        null=True,
        blank=True,
        verbose_name="برند",
)
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



class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name="محصول",
    )

    sku = models.CharField(
        "کد اختصاصی کالا",
        max_length=100,
        unique=True,
    )

    color = models.CharField(
        "رنگ",
        max_length=100,
        blank=True,
    )

    storage = models.CharField(
        "حافظه",
        max_length=100,
        blank=True,
    )

    price = models.PositiveBigIntegerField("قیمت")

    stock = models.PositiveIntegerField(
        "موجودی",
        default=0,
    )

    is_active = models.BooleanField(
        "فعال",
        default=True,
    )

    def clean(self):
        super().clean()

        errors = {}

        if not self.color.strip() and not self.storage.strip():
            errors["color"] = "حداقل رنگ یا حافظه باید مشخص باشد."

        if self.price is not None and self.price <= 0:
            errors["price"] = "قیمت باید بیشتر از صفر باشد."

        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = "تنوع محصول"
        verbose_name_plural = "تنوع‌های محصول"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "color", "storage"],
                name="unique_product_variant_combination",
            ),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.sku}"



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


