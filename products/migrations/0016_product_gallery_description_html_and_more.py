from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0015_category_urls'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='gallery_description_html',
            field=models.TextField(blank=True, max_length=160000, verbose_name='توضیحات گالری قالب\u200cبندی\u200cشده'),
        ),
        migrations.AddField(
            model_name='product',
            name='long_description_html',
            field=models.TextField(blank=True, max_length=160000, verbose_name='توضیحات کامل قالب\u200cبندی\u200cشده'),
        ),
    ]
