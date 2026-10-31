import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0002_page_footer_label_page_footer_order_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BannerSet',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('draft', models.JSONField(default=list)),
                ('published', models.JSONField(default=list)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'permissions': [('publish_bannerset', 'Can publish store banners')],
                'constraints': [models.CheckConstraint(condition=models.Q(('pk', 1)), name='cms_banners_singleton')],
            },
        ),
    ]
