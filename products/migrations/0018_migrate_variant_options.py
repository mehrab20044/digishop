import hashlib
import json

from django.db import migrations


def migrate_options(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Variant = apps.get_model("products", "ProductVariant")
    db = schema_editor.connection.alias
    for product in Product.objects.using(db).iterator():
        variants = list(Variant.objects.using(db).filter(product_id=product.pk))
        if not variants:
            continue
        axes = []
        for key, label in [("color", "رنگ"), ("storage", "حافظه")]:
            values = list(dict.fromkeys(getattr(v, key) for v in variants if getattr(v, key)))
            if values:
                axes.append({"key": key, "label": label, "values": values, "required": all(bool(getattr(v, key)) for v in variants)})
        Product.objects.using(db).filter(pk=product.pk).update(variant_schema=axes)
        for variant in variants:
            options = {key: getattr(variant, key) for key in ["color", "storage"] if getattr(variant, key)}
            if not options:
                continue
            fingerprint = hashlib.sha256(json.dumps(options, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            Variant.objects.using(db).filter(pk=variant.pk).update(options=options, combination_key=fingerprint)


class Migration(migrations.Migration):
    dependencies = [("products", "0017_catalog_attributes")]
    operations = [migrations.RunPython(migrate_options, migrations.RunPython.noop)]
