import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PageImage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('file', models.ImageField(upload_to='cms/images/%Y/%m/')),
                ('width', models.PositiveIntegerField()),
                ('height', models.PositiveIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Page',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=160, verbose_name='عنوان صفحه')),
                ('slug', models.SlugField(allow_unicode=True, max_length=120, unique=True, verbose_name='نامک')),
                ('seo_title', models.CharField(blank=True, max_length=180)),
                ('seo_description', models.CharField(blank=True, max_length=320)),
                ('blocks', models.JSONField(default=list)),
                ('published', models.JSONField(default=dict, editable=False)),
                ('is_published', models.BooleanField(default=False)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('published_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at', '-pk'],
                'permissions': [('publish_page', 'Can publish or hide pages')],
                'constraints': [models.CheckConstraint(condition=models.Q(('revision__gte', 1)), name='cms_page_revision_positive')],
            },
        ),
    ]
