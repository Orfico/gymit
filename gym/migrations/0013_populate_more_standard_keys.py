"""
Collega agli standard i nuovi esercizi aggiunti alle tabelle (panca inclinata,
squat frontale, stacco rumeno, hip thrust, panca presa stretta, curl con
bilanciere, stacco sumo), per nome esatto come in 0011.

Solo dove la chiave è ancora vuota: se un admin ha già scelto uno standard a
mano, non viene toccato. Gli esercizi con nomi diversi si collegano dall'app.
"""

from django.db import migrations

MAPPING = {
    'incline_bench_press': ['incline bench press', 'panca inclinata'],
    'front_squat': ['front squat', 'squat frontale'],
    'romanian_deadlift': ['romanian deadlift', 'rdl', 'stacco rumeno'],
    'hip_thrust': ['hip thrust'],
    'close_grip_bench_press': [
        'close grip bench press', 'panca presa stretta', 'panca piana presa stretta',
    ],
    'barbell_curl': ['barbell curl', 'curl bilanciere', 'curl con bilanciere'],
    'sumo_deadlift': ['sumo deadlift', 'stacco sumo'],
}


def populate_standard_keys(apps, schema_editor):
    Exercise = apps.get_model('gym', 'Exercise')

    for key, names in MAPPING.items():
        for name in names:
            Exercise.objects.filter(
                name__iexact=name, standard_key__isnull=True
            ).update(standard_key=key)


def clear_standard_keys(apps, schema_editor):
    Exercise = apps.get_model('gym', 'Exercise')
    Exercise.objects.filter(standard_key__in=list(MAPPING)).update(standard_key=None)


class Migration(migrations.Migration):

    dependencies = [
        ('gym', '0012_backfill_user_profiles'),
    ]

    operations = [
        migrations.RunPython(populate_standard_keys, clear_standard_keys),
    ]
