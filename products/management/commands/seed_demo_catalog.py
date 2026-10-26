"""Add the bundled fictional catalog without overwriting existing products."""
import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from products.models import (
    Attribute, Brand, Category, CategoryAttribute, Product,
    ProductAttributeValue, ProductImage, ProductVariant,
)


def named_record(model, name, slug):
    by_slug = model.objects.filter(slug=slug).first()
    if by_slug:
        if by_slug.name != name:
            raise CommandError(f"Conflicting {model.__name__} slug: {slug}")
        return by_slug
    by_name = model.objects.filter(name=name).first()
    if by_name:
        return by_name
    record = model(name=name, slug=slug)
    record.full_clean()
    record.save()
    return record


class Command(BaseCommand):
    help = "Create 8 fictional DigiShop products with photos, variants and specifications. Existing slugs are skipped."

    def add_arguments(self, parser):
        parser.add_argument('--assets', default=str(Path(settings.BASE_DIR) / 'demo_catalog'))
        parser.add_argument('--dry-run', action='store_true', help='Validate files and report what would be created; write nothing.')

    def handle(self, *args, **options):
        root = Path(options['assets']).expanduser().resolve()
        try:
            catalog = json.loads((root / 'products.json').read_text(encoding='utf-8'))
            rows = catalog['products']
            if catalog['price_unit'] != 'تومان' or len(rows) != 8:
                raise ValueError('Expected exactly 8 products priced in toman.')
            slugs = set()
            skus = set()
            for row in rows:
                if not row['slug'].startswith('digishop-demo-') or row['slug'] in slugs:
                    raise ValueError('Invalid or duplicate demo slug.')
                slugs.add(row['slug'])
                image_path = (root / row['image']).resolve()
                if root not in image_path.parents or not image_path.is_file():
                    raise ValueError(f"Image is missing or outside assets folder: {row['image']}")
                image = ProductImage(image=SimpleUploadedFile(image_path.name, image_path.read_bytes()))
                # Image field validators run without needing a saved product.
                image.full_clean(exclude=['product'], validate_unique=False, validate_constraints=False)
                if not row['variants'] or not row['attributes']:
                    raise ValueError('Every product must have variants and specifications.')
                for variant in row['variants']:
                    if variant['sku'] in skus or variant['price'] <= 0 or variant['stock'] < 0:
                        raise ValueError('Duplicate SKU or invalid variant price/stock.')
                    skus.add(variant['sku'])
        except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
            raise CommandError(f'Catalog validation failed: {exc}') from exc

        existing = set(Product.objects.filter(slug__in=slugs).values_list('slug', flat=True))
        pending = [row for row in rows if row['slug'] not in existing]
        self.stdout.write(f'Fictional demo data | unit: toman | new: {len(pending)} | existing/skipped: {len(existing)}')
        if options['dry_run']:
            for row in pending:
                self.stdout.write(f"  + {row['name']} | {len(row['variants'])} variants")
            self.stdout.write(self.style.SUCCESS('Files validated. Dry run: no database or media writes.'))
            return

        created_files = []
        try:
            with transaction.atomic():
                for row in pending:
                    category = named_record(Category, **row['category'])
                    brand = named_record(Brand, **catalog['brand'])
                    variants = row['variants']
                    available = [variant for variant in variants if variant['stock'] > 0]
                    base_price = min(variant['price'] for variant in (available or variants))
                    product = Product(
                        name=row['name'], slug=row['slug'], category=category, brand=brand,
                        description=row['long_description'], short_description=row['short_description'],
                        long_description=row['long_description'], gallery_description=row['gallery_description'],
                        price=base_price, stock=sum(variant['stock'] for variant in variants),
                        is_active=True, status=Product.Status.PUBLISHED,
                    )
                    product.full_clean()
                    product.save()
                    for values in variants:
                        variant = ProductVariant(product=product, is_active=True, **values)
                        variant.full_clean()
                        variant.save()
                    for label, value in row['attributes'].items():
                        attribute = named_record(Attribute, label, f'digishop-demo-{slugify(label, allow_unicode=True)}')
                        CategoryAttribute.objects.get_or_create(category=category, attribute=attribute)
                        attribute_value = ProductAttributeValue(product=product, attribute=attribute, value=value)
                        attribute_value.full_clean()
                        attribute_value.save()
                    path = root / row['image']
                    photo = ProductImage(
                        product=product, image=SimpleUploadedFile(path.name, path.read_bytes()),
                        title=row['name'], alt_text=row['image_alt'],
                        caption='تصویر تولیدشده با هوش مصنوعی؛ کالای نمونه و غیرواقعی',
                        description=row['gallery_description'], is_primary=True, sort_order=0,
                    )
                    photo.full_clean()
                    photo.image.save(f"{row['slug']}{path.suffix.lower()}", photo.image, save=False)
                    created_files.append((photo.image.storage, photo.image.name))
                    photo.save()
                    self.stdout.write(f"Created: {row['name']}")
        except Exception as exc:
            # DB rollback does not roll back media storage. Delete only this run's new files.
            for storage, name in created_files:
                if not ProductImage.objects.filter(image=name).exists() and not Product.objects.filter(image=name).exists():
                    try:
                        storage.delete(name)
                    except OSError:
                        self.stderr.write(f'Could not clean orphaned file: {name}')
            raise CommandError(f'Import rolled back: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(f'Done. Created {len(pending)} products; skipped {len(existing)}. Existing products were not changed.'))
