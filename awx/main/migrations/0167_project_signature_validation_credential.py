# Generated by Django 3.2.13 on 2022-08-24 14:02

from django.db import migrations, models
import django.db.models.deletion

from awx.main.models import CredentialType
from awx.main.utils.common import set_current_apps


def setup_tower_managed_defaults(apps, schema_editor):
    set_current_apps(apps)
    CredentialType.setup_tower_managed_defaults(apps)


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0166_alter_jobevent_host'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='signature_validation_credential',
            field=models.ForeignKey(
                blank=True,
                default=None,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='projects_signature_validation',
                to='main.credential',
                help_text='An optional credential used for validating files in the project against unexpected changes.',
            ),
        ),
        migrations.AlterField(
            model_name='credentialtype',
            name='kind',
            field=models.CharField(
                choices=[
                    ('ssh', 'Machine'),
                    ('vault', 'Vault'),
                    ('net', 'Network'),
                    ('scm', 'Source Control'),
                    ('cloud', 'Cloud'),
                    ('registry', 'Container Registry'),
                    ('token', 'Personal Access Token'),
                    ('insights', 'Insights'),
                    ('external', 'External'),
                    ('kubernetes', 'Kubernetes'),
                    ('galaxy', 'Galaxy/Automation Hub'),
                    ('cryptography', 'Cryptography'),
                ],
                max_length=32,
            ),
        ),
        migrations.RunPython(setup_tower_managed_defaults),
    ]
