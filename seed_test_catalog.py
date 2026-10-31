from django.conf import settings
from django.db import transaction

from products.models import Category, Product, ProductImage, ProductVariant
from products.services.category_service import category_tree_write_lock

PREFIX = "uxdemo-v1"

BRANCHES = [
    ("کالای دیجیتال", [
        ("لپ‌تاپ", ["گیمینگ", "دانشجویی"]),
        ("موبایل", ["اقتصادی", "پرچم‌دار"]),
    ]),
    ("پوشاک", [
        ("مردانه", ["پیراهن", "شلوار"]),
        ("اکسسوری", ["کلاه", "کمربند"]),
    ]),
    ("خانه و آشپزخانه", [
        ("ظروف", ["ماگ", "بشقاب"]),
        ("روشنایی", ["چراغ مطالعه", "چراغ دیواری"]),
    ]),
    ("ورزش و سفر", [
        ("کمپینگ", ["کوله‌پشتی", "چادر"]),
        ("ورزشی", ["توپ", "دمبل"]),
    ]),
    ("لوازم تحریر", [
        ("نوشت‌افزار", ["خودکار", "مداد"]),
        ("کاغذی", ["دفتر", "دفتر طراحی"]),
    ]),
    ("ابزار", [
        ("دستی", ["پیچ‌گوشتی", "آچار"]),
        ("برقی", ["دریل", "پیچ‌گوشتی برقی"]),
    ]),
]


def get_category(name, slug, parent=None):
    obj, created = Category.objects.get_or_create(
        slug=slug,
        defaults={
            "name": name,
            "parent": parent,
            "description": (
                f"توضیحات آزمایشی دسته‌بندی {name}؛ "
                "برای تست نمایش زیرشاخه‌ها و محصولات فروشگاه."
            ),
        },
    )
    if obj.parent_id != (parent.pk if parent else None):
        raise RuntimeError(f"والد دسته آزمایشی تغییر کرده: {slug}")
    return obj


if not settings.DEBUG:
    raise RuntimeError("این اسکریپت فقط برای محیط توسعه است.")

created = 0
skipped = 0

with transaction.atomic(), category_tree_write_lock():
    # فقط آدرس تصاویر موجود را استفاده می‌کنیم؛ فایل اصلی تغییر نمی‌کند.
    pictures = list(
        ProductImage.objects.exclude(image="")
        .exclude(product__slug__startswith=PREFIX)
        .values_list("image", flat=True)[:30]
    )

    if not pictures:
        raise RuntimeError("ابتدا برای یک محصول، تصویر گالری ثبت کن.")

    for root_index, (root_name, sections) in enumerate(BRANCHES):
        root_slug = f"{PREFIX}-category-{root_index}"
        root = get_category(root_name + " ـ تست", root_slug)

        for section_index, (section_name, leaves) in enumerate(sections):
            section_slug = f"{root_slug}-{section_index}"
            section = get_category(section_name, section_slug, root)

            for leaf_index, leaf_name in enumerate(leaves):
                leaf_slug = f"{section_slug}-{leaf_index}"
                leaf = get_category(leaf_name, leaf_slug, section)

                for index in range(10):
                    code = f"{root_index}-{section_index}-{leaf_index}-{index}"
                    slug = f"{PREFIX}-product-{code}"

                    if Product.objects.filter(slug=slug).exists():
                        skipped += 1
                        continue

                    base_price = 150000 + root_index * 200000 + index * 50000
                    has_variants = index % 2 == 1
                    unavailable = index == 0

                    item = Product(
                        name=f"{leaf_name} آزمایشی مدل {code}",
                        slug=slug,
                        category=leaf,
                        price=base_price,
                        stock=0 if unavailable or has_variants else 12,
                        status=Product.Status.DRAFT,
                        is_active=True,
                        short_description="محصول خیالی برای تست فروشگاه.",
                        long_description=(
                            f"محصول آزمایشی {leaf_name} در دسته {section_name}.\n"
                            "قیمت و موجودی ساختگی هستند. تصاویر از محصولات "
                            "موجود برای تست نمایش استفاده شده‌اند و مربوط "
                            "به این کالا نیستند."
                        ),
                        variant_schema=(
                            [{
                                "key": "color",
                                "label": "رنگ",
                                "values": ["مشکی", "سفید", "آبی"],
                                "required": True,
                            }]
                            if has_variants else []
                        ),
                    )
                    item.full_clean()
                    item.save()
                    item.categories.add(leaf)

                    if has_variants:
                        for variant_index, color in enumerate(
                            ["مشکی", "سفید", "آبی"]
                        ):
                            variant = ProductVariant(
                                product=item,
                                sku=f"UXDEMO-V1-{code}-{variant_index}",
                                options={"color": color},
                                price=base_price + variant_index * 50000,
                                stock=0 if variant_index == 2 else 8,
                                is_active=True,
                            )
                            variant.full_clean()
                            variant.save()

                    for image_index in range(3):
                        ProductImage.objects.create(
                            product=item,
                            image=pictures[(index + image_index) % len(pictures)],
                            is_primary=image_index == 0,
                            sort_order=image_index,
                        )

                    item.status = Product.Status.PUBLISHED
                    item.full_clean()
                    item.save()
                    created += 1

    print("Created:", created)
    print("Skipped:", skipped)
    print(
        "Total demo products:",
        Product.objects.filter(
            slug__startswith=f"{PREFIX}-product-"
        ).count(),
    )
