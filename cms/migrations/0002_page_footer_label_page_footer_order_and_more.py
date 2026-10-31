import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def preserve_existing_publication(apps, schema_editor):
    Page = apps.get_model("cms", "Page")
    for page in Page.objects.using(schema_editor.connection.alias).exclude(published={}).iterator():
        snapshot = dict(page.published)
        for key, value in {"layout": "simple", "footer_visible": True, "footer_label": "", "footer_order": 0}.items():
            snapshot.setdefault(key, value)
        Page.objects.using(schema_editor.connection.alias).filter(pk=page.pk).update(published=snapshot)


class Migration(migrations.Migration):

    dependencies = [
        ('cms', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='page',
            name='footer_label',
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name='page',
            name='footer_order',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='page',
            name='footer_visible',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='page',
            name='layout',
            field=models.CharField(default='simple', max_length=20),
        ),
        migrations.CreateModel(
            name='SiteTheme',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('draft', models.JSONField(default=dict)),
                ('published', models.JSONField(default=dict)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'permissions': [('publish_sitetheme', 'Can publish store appearance')],
                'constraints': [models.CheckConstraint(condition=models.Q(('pk', 1)), name='cms_theme_singleton')],
            },
        ),
        migrations.RunPython(preserve_existing_publication, migrations.RunPython.noop),
    ]
