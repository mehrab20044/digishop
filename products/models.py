from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models

from .validators import (
    validate_product_image_content,
    validate_product_image_size,
)


class Category(models.Model):
    name = models.CharField(
        "نام دسته‌بندی",
        max_length=100
    )
    slug = models.SlugField(
        "نامک آدرس", max_length=120, unique=True, allow_unicode=True,
        blank=True,
    )

    def clean_fields(self, exclude=None):
        from products.services.category_url_service import prepare_slug
        prepare_slug(self)
        super().clean_fields(exclude=exclude)

    def save(self, *args, **kwargs):
        from products.services.category_url_service import save_with_urls
        return save_with_urls(self, super().save, args, kwargs)

    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        null=True,
        blank=True,
        verbose_name="دستهٔ والد",
    )

    related_categories = models.ManyToManyField(
        "self",
        symmetrical=True,
        blank=True,
        verbose_name="دسته‌های مرتبط",
    )

    description = models.TextField(
        "توضیح دسته‌بندی",
        blank=True,
    )
    sort_order = models.PositiveIntegerField(
        "ترتیب نمایش",
        default=0,
    )

    class Meta:
        verbose_name = "دسته‌بندی"
        verbose_name_plural = "دسته‌بندی‌ها"
        ordering = ["sort_order", "name", "id"]
        indexes = [
            models.Index(
                fields=["parent", "sort_order"],
                name="products_cat_parent_sort_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["parent", "name"],
                name="products_cat_unique_sibling",
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=models.Q(parent__isnull=True),
                name="products_cat_unique_root",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(parent__isnull=True)
                    | ~models.Q(parent=models.F("pk"))
                ),
                name="products_category_not_own_parent",
            ),
        ]

    def clean(self):
        super().clean()

        if not self.name or not self.name.strip():
            raise ValidationError({
                "name": "نام دسته‌بندی الزامی است.",
            })

        if self.parent_id is None:
            return

        visited = set()

        if self.pk is not None:
            visited.add(self.pk)

        current_id = self.parent_id

        while current_id is not None:
            if current_id in visited:
                raise ValidationError({
                    "parent": (
                        "این انتخاب در دسته‌بندی‌ها چرخه ایجاد می‌کند."
                    ),
                })

            visited.add(current_id)

            parent = (
                Category.objects.filter(pk=current_id)
                .values("parent_id")
                .first()
            )

            if parent is None:
                raise ValidationError({
                    "parent": "دستهٔ والد وجود ندارد.",
                })

            current_id = parent["parent_id"]

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

    value_type = models.CharField(max_length=12, default="text", choices=[("text", "متن"), ("number", "عدد"), ("boolean", "بله/خیر"), ("choice", "انتخابی")])
    unit = models.CharField(max_length=30, blank=True)
    choices = models.JSONField(default=list, blank=True)

    def clean(self):
        super().clean()
        from products.services.attribute_service import (
            normalize_value,
            validate_definition,
        )
        validate_definition(self)
        if self.pk:
            from products.services.category_service import category_tree_write_lock
            with category_tree_write_lock():
                for existing in self.product_values.all():
                    normalize_value(self, existing.value)

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

    required = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)

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

        from products.services.attribute_service import effective_rules, normalize_value
        if self.attribute_id not in effective_rules(self.product.category_id):
            raise ValidationError({"attribute": "این ویژگی برای دستهٔ اصلی یا والدهای آن تعریف نشده است."})
        self.value = normalize_value(self.attribute, self.value)

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
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        PUBLISHED = "published", "منتشرشده"
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="دسته‌بندی اصلی",
    )

    categories = models.ManyToManyField(
        Category,
        related_name="listed_products",
        blank=True,
        verbose_name="دسته‌بندی‌های محصول",
    )

    variant_schema = models.JSONField(default=list, blank=True)
    catalog_revision = models.PositiveIntegerField(default=1, editable=False)

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
    long_description_html = models.TextField("توضیحات کامل قالب‌بندی‌شده", blank=True, max_length=160000)
    gallery_description_html = models.TextField("توضیحات گالری قالب‌بندی‌شده", blank=True, max_length=160000)
    price = models.PositiveBigIntegerField("قیمت")
    stock = models.PositiveIntegerField("موجودی", default=0)
    image = models.ImageField(
        "تصویر قدیمی",
        upload_to="products/",
        blank=True,
    )

    is_active = models.BooleanField("فعال و قابل انتشار", default=True)
    status = models.CharField(
        "وضعیت انتشار",
        max_length=20,
        choices=Status.choices,
        default=Status.PUBLISHED,
    )
    created_at = models.DateTimeField("زمان ایجاد", auto_now_add=True)


    def save(self, *args, **kwargs):
        from products.services.richtext_service import sync_product_richtext
        updates = sync_product_richtext(self, kwargs.get("update_fields"))
        if updates is not None:
            kwargs["update_fields"] = updates
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        from products.services.richtext_service import sanitize_richtext
        sanitize_richtext(self.long_description_html)
        sanitize_richtext(self.gallery_description_html)
        from products.services.attribute_service import validate_axes, validate_options
        validate_axes(self.variant_schema)
        if self.pk:
            for variant in self.variants.all():
                if variant.options:
                    validate_options(self.variant_schema, variant.options)


        if self.status != self.Status.PUBLISHED:
            return

        if self.pk:
            from products.services.attribute_service import validate_product_specs
            validate_product_specs(self, require_all=True)

        # محصولات جدید هنوز Variant ذخیره‌شده ندارند.
        if self.pk and self.variants.exists():
            return

        if self.price is not None and self.price <= 0:
            raise ValidationError({
                "price": "قیمت محصول منتشرشده باید بیشتر از صفر باشد."
            })

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

    options = models.JSONField(default=dict, blank=True)
    combination_key = models.CharField(max_length=64, blank=True, default="", editable=False)

    @property
    def display_name(self):
        if not self.options or set(self.options) <= {"color", "storage"}:
            return " / ".join(filter(None, [self.options.get("color", self.color), self.options.get("storage", self.storage)]))
        labels = {axis["key"]: axis["label"] for axis in self.product.variant_schema}
        return " / ".join(f"{labels.get(key, key)}: {value}" for key, value in self.options.items())

    def clean(self):
        super().clean()

        errors = {}

        if not self.options and self.product_id and self.product.variant_schema:
            self.options = {key: value for key, value in [("color", self.color), ("storage", self.storage)] if value}
        if self.options:
            from products.services.attribute_service import validate_options
            self.options, self.combination_key = validate_options(self.product.variant_schema, self.options)
            if not set(self.options) <= {"color", "storage"}:
                self.color = self.storage = ""
        if not self.options and not self.color.strip() and not self.storage.strip():
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
                condition=(~models.Q(color="", storage="") | models.Q(options={})),
            ),
            models.UniqueConstraint(fields=["product", "combination_key"], condition=~models.Q(combination_key=""), name="products_unique_variant_options"),
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


class CategoryURL(models.Model):
    path = models.CharField(max_length=2048)
    digest = models.CharField(max_length=64, unique=True)

    def save(self, *args, **kwargs):
        import hashlib
        self.digest = hashlib.sha256(self.path.encode("utf-8")).hexdigest()
        return super().save(*args, **kwargs)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="url_history")

    class Meta:
        verbose_name = "سابقهٔ آدرس دسته"
