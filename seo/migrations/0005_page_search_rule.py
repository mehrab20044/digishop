from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("seo", "0004_alter_seosettings_version_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="PageSearchRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=16, choices=[(value, value) for value in ("home", "catalog", "directory", "product", "category", "page")])),
                ("object_id", models.PositiveBigIntegerField(default=0)),
                ("crawl", models.CharField(max_length=8, default="inherit", choices=[("inherit", "پیش‌فرض"), ("allow", "مجاز"), ("block", "مسدود")])),
                ("indexing", models.CharField(max_length=8, default="inherit", choices=[("inherit", "پیش‌فرض"), ("index", "مجاز"), ("noindex", "غیرمجاز")])),
                ("version", models.PositiveIntegerField(default=0, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "قانون سئوی صفحه", "verbose_name_plural": "قوانین سئوی صفحات", "constraints": [models.UniqueConstraint(fields=("kind", "object_id"), name="seo_unique_page_rule")]},
        ),
    ]
