"""
Collega gli esercizi già presenti agli strength standard, per nome.

Il confronto è esatto (senza distinzione tra maiuscole e minuscole) e non per
sottostringa, di proposito: "Panca Piana Presa Stretta" o "Squat Frontale"
contengono il nome di un esercizio di riferimento ma hanno carichi diversi, e
confrontarli con quegli standard darebbe un benchmark sbagliato. Gli esercizi
non riconosciuti restano senza chiave e si possono collegare dall'admin.
"""

from django.db import migrations

MAPPING = {
    'bench_press': ['bench press', 'panca piana', 'distensioni su panca', 'panca'],
    'squat': ['squat', 'back squat', 'barbell squat'],
    'deadlift': ['deadlift', 'stacco', 'stacco da terra'],
    'overhead_press': ['overhead press', 'ohp', 'military press', 'press militare', 'lento avanti'],
    'barbell_row': ['barbell row', 'bent over row', 'rematore', 'rematore con bilanciere'],
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
        ('gym', '0010_userprofile_exercise_standard_key'),
    ]

    operations = [
        migrations.RunPython(populate_standard_keys, clear_standard_keys),
    ]
