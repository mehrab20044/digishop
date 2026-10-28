from django.db import migrations


def copy_primary_categories(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    Membership = Product.categories.through
    database = schema_editor.connection.alias

    batch = []

    products = (
        Product.objects.using(database)
        .values_list("pk", "category_id")
        .iterator(chunk_size=1000)
    )

    for product_id, category_id in products:
        if category_id is None:
            continue

        batch.append(
            Membership(
                product_id=product_id,
                category_id=category_id,
            )
        )

        if len(batch) >= 1000:
            Membership.objects.using(database).bulk_create(
                batch,
                batch_size=1000,
                ignore_conflicts=True,
            )
            batch.clear()

    if batch:
        Membership.objects.using(database).bulk_create(
            batch,
            batch_size=1000,
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        (
            "products",
            "0011_alter_category_options_category_description_and_more",
        ),
    ]

    operations = [
        migrations.RunPython(
            copy_primary_categories,
            reverse_code=migrations.RunPython.noop,
        ),
    ]