from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0013_alter_category_slug"),
    ]

    operations = [
        migrations.AlterField(
            model_name="category",
            name="name",
            field=models.CharField("نام دسته‌بندی", max_length=100),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                fields=("parent", "name"),
                name="products_cat_unique_sibling",
            ),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=models.UniqueConstraint(
                fields=("name",),
                condition=models.Q(parent__isnull=True),
                name="products_cat_unique_root",
            ),
        ),
    ]
