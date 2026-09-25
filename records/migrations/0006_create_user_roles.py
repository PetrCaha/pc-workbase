from django.db import migrations


ROLE_GROUPS = ('Administrátor', 'Správce', 'Člen')


def create_user_roles(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    groups = {name: Group.objects.get_or_create(name=name)[0] for name in ROLE_GROUPS}
    for user in User.objects.all():
        group = groups['Administrátor'] if user.is_superuser or user.is_staff else groups['Člen']
        user.groups.add(group)


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('records', '0005_customerchange'),
    ]

    operations = [
        migrations.RunPython(create_user_roles, migrations.RunPython.noop),
    ]
