"""
Collega agli standard gli esercizi coi manubri del catalogo, per nome esatto
come in 0011 e 0013, e solo dove la chiave è ancora vuota.

"Shoulder press" da solo non è mappato: può essere una macchina o il bilanciere,
e il benchmark coi manubri sarebbe sbagliato. Si collega dall'app, se serve.
"""

from django.db import migrations

MAPPING = {
    'dumbbell_bench_press': [
        'dumbbell bench press', 'panca piana manubri', 'panca manubri',
        'panca piana con manubri',
    ],
    'incline_dumbbell_bench_press': [
        'incline dumbbell bench press', 'panca inclinata manubri',
        'panca inclinata con manubri',
    ],
    'dumbbell_shoulder_press': [
        'dumbbell shoulder press', 'press manubri', 'lento con manubri',
    ],
    'dumbbell_curl': ['dumbbell curl', 'curl manubri', 'curl con manubri'],
    'hammer_curl': ['hammer curl', 'curl a martello', 'curl martello'],
    'dumbbell_lateral_raise': [
        'dumbbell lateral raise', 'lateral raise', 'alzate laterali',
    ],
    'dumbbell_fly': ['dumbbell fly', 'croci manubri', 'croci con manubri'],
    'dumbbell_row': [
        'dumbbell row', 'rematore con manubrio', 'rematore manubrio',
        'rematore con manubri',
    ],
    'dumbbell_shrug': ['dumbbell shrug', 'scrollate con manubri', 'scrollate manubri'],
    'goblet_squat': ['goblet squat'],
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
        ('gym', '0015_userprofile_dumbbell_weight_mode'),
    ]

    operations = [
        migrations.RunPython(populate_standard_keys, clear_standard_keys),
    ]
