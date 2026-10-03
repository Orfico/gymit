"""
Crea il profilo fisico (vuoto) per gli utenti registrati prima della sua
introduzione: il signal di auto-creazione scatta solo sui nuovi account.

Idempotente: chi ha già un profilo non viene toccato. Tornare indietro non
cancella nulla, perché i profili potrebbero nel frattempo contenere dati
inseriti dagli utenti.
"""

from django.conf import settings
from django.db import migrations


def backfill_profiles(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split('.')
    User = apps.get_model(app_label, model_name)
    UserProfile = apps.get_model('gym', 'UserProfile')

    missing = User.objects.filter(userprofile__isnull=True)
    UserProfile.objects.bulk_create(
        [UserProfile(user_id=pk) for pk in missing.values_list('pk', flat=True)]
    )


class Migration(migrations.Migration):

    dependencies = [
        ('gym', '0011_populate_standard_keys'),
    ]

    operations = [
        migrations.RunPython(backfill_profiles, migrations.RunPython.noop),
    ]
