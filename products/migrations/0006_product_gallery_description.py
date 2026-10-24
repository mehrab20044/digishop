from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0005_validate_product_image_content"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="gallery_description",
            field=models.TextField(blank=True),
        ),
    ]
