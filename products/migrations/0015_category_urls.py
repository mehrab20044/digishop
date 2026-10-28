import hashlib

import django.db.models.deletion
from django.db import migrations, models


def seed(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    CategoryURL = apps.get_model("products", "CategoryURL")
    rows = {r.pk: r for r in Category.objects.using(schema_editor.connection.alias).all()}
    for row in rows.values():
        parts, seen, current = [], set(), row
        while current is not None:
            if current.pk in seen:
                raise RuntimeError("Category cycle; fix before migrating.")
            seen.add(current.pk)
            parts.append(current.slug)
            current = rows.get(current.parent_id)
        CategoryURL.objects.using(schema_editor.connection.alias).create(category_id=row.pk, path="/".join(reversed(parts)), digest=hashlib.sha256("/".join(reversed(parts)).encode("utf-8")).hexdigest())


def readable_generated_slugs(apps, schema_editor):
    import re
    import unicodedata

    from django.utils.text import slugify
    Category = apps.get_model("products", "Category")
    CategoryURL = apps.get_model("products", "CategoryURL")
    alias = schema_editor.connection.alias
    rows = list(Category.objects.using(alias).order_by("pk"))
    used = {row.slug for row in rows}
    digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩كي", "01234567890123456789کی")
    for row in rows:
        if not re.fullmatch(r"category-[0-9a-fA-F-]{36}", row.slug):
            continue
        value = unicodedata.normalize("NFKC", row.name).translate(digits)
        value = re.sub(r"[\s\u200c\u200d_]+", "-", value)
        base = slugify(value, allow_unicode=True).strip("-")[:110].rstrip("-")
        if not base:
            continue
        candidate, suffix = base, 2
        while candidate in used:
            candidate = f"{base}-{suffix}"
            suffix += 1
        row.slug = candidate
        used.add(candidate)
        Category.objects.using(alias).filter(pk=row.pk).update(slug=candidate)
    by_id = {row.pk: row for row in rows}
    for row in rows:
        parts, current = [], row
        while current is not None:
            parts.append(current.slug)
            current = by_id.get(current.parent_id)
        history, _ = CategoryURL.objects.using(alias).get_or_create(path="/".join(reversed(parts)), defaults={"category_id": row.pk, "digest": hashlib.sha256("/".join(reversed(parts)).encode("utf-8")).hexdigest()})
        if history.category_id != row.pk:
            raise RuntimeError("Category URL conflict; migration rolled back.")


class Migration(migrations.Migration):
    dependencies = [("products", "0014_category_sibling_names")]
    operations = [
        migrations.AlterField(model_name="category", name="slug", field=models.SlugField("نامک آدرس", max_length=120, unique=True, allow_unicode=True, blank=True)),
        migrations.CreateModel(name="CategoryURL", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("path", models.CharField(max_length=2048)),
            ("digest", models.CharField(max_length=64, unique=True)),
            ("category", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="url_history", to="products.category")),
        ], options={"verbose_name": "سابقهٔ آدرس دسته"}),
        migrations.RunPython(seed, migrations.RunPython.noop),
        migrations.RunPython(readable_generated_slugs, migrations.RunPython.noop),
    ]
