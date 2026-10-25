from django.conf import settings
from django.db import migrations


def create_existing_profiles(apps, schema_editor):
    label, name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(label, name)
    Profile = apps.get_model("accounts", "Profile")
    alias = schema_editor.connection.alias

    users = (
        User.objects.using(alias)
        .exclude(
            pk__in=Profile.objects.using(alias).values(
                "user_id",
            ),
        )
        .values_list("pk", flat=True)
    )

    batch = []

    for user_id in users.iterator(chunk_size=500):
        batch.append(Profile(user_id=user_id))

        if len(batch) == 500:
            Profile.objects.using(alias).bulk_create(
                batch,
                ignore_conflicts=True,
            )
            batch = []

    if batch:
        Profile.objects.using(alias).bulk_create(
            batch,
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_profile_addresses"),
    ]

    operations = [
        migrations.RunPython(
            create_existing_profiles,
            migrations.RunPython.noop,
        ),
    ]