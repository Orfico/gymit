"""
Comando di gestione per popolare il catalogo con gli esercizi più comuni.
Uso: python manage.py seed_exercises
"""
from django.core.management.base import BaseCommand
from gym.models import Exercise, MuscleGroup


EXERCISES = [
    # Petto
    ('Panca Piana', MuscleGroup.CHEST, 'Esercizio fondamentale per il petto con bilanciere'),
    ('Panca Inclinata', MuscleGroup.CHEST, 'Angolazione 30-45° per enfatizzare il pettorale alto'),
    ('Panca Piana Manubri', MuscleGroup.CHEST, ''),
    ('Croci ai Cavi', MuscleGroup.CHEST, ''),
    ('Dips', MuscleGroup.CHEST, 'Corpo libero, ottimo per petto e tricipiti'),

    # Schiena
    ('Stacco da Terra', MuscleGroup.BACK, 'Esercizio multiarticolare fondamentale'),
    ('Trazioni', MuscleGroup.BACK, 'Corpo libero, presa prona o supina'),
    ('Lat Machine', MuscleGroup.BACK, ''),
    ('Rematore con Bilanciere', MuscleGroup.BACK, ''),
    ('Rematore con Manubrio', MuscleGroup.BACK, 'Unilaterale'),
    ('Pulley Basso', MuscleGroup.BACK, ''),

    # Spalle
    ('Press Militare', MuscleGroup.SHOULDERS, 'Bilanciere, in piedi o seduto'),
    ('Press Manubri', MuscleGroup.SHOULDERS, ''),
    ('Alzate Laterali', MuscleGroup.SHOULDERS, ''),
    ('Alzate Frontali', MuscleGroup.SHOULDERS, ''),
    ('Face Pull', MuscleGroup.SHOULDERS, 'Cavi, ottimo per i posteriori'),

    # Bicipiti
    ('Curl Bilanciere', MuscleGroup.BICEPS, ''),
    ('Curl Manubri', MuscleGroup.BICEPS, ''),
    ('Curl a Martello', MuscleGroup.BICEPS, ''),
    ('Curl ai Cavi', MuscleGroup.BICEPS, ''),

    # Tricipiti
    ('French Press', MuscleGroup.TRICEPS, 'Bilanciere o manubrio'),
    ('Tricipiti ai Cavi', MuscleGroup.TRICEPS, 'Pushdown con corda o barra'),
    ('Dips stretti', MuscleGroup.TRICEPS, ''),
    ('Panca Piana Presa Stretta', MuscleGroup.TRICEPS, ''),

    # Gambe
    ('Squat', MuscleGroup.LEGS, 'Esercizio fondamentale per le gambe'),
    ('Squat Frontale', MuscleGroup.LEGS, ''),
    ('Leg Press', MuscleGroup.LEGS, ''),
    ('Affondi', MuscleGroup.LEGS, ''),
    ('Leg Extension', MuscleGroup.LEGS, ''),
    ('Leg Curl', MuscleGroup.LEGS, ''),
    ('Romanian Deadlift', MuscleGroup.LEGS, 'Ottimo per femorali e glutei'),

    # Glutei
    ('Hip Thrust', MuscleGroup.GLUTES, ''),
    ('Glute Bridge', MuscleGroup.GLUTES, ''),

    # Addome
    ('Crunch', MuscleGroup.ABS, ''),
    ('Plank', MuscleGroup.ABS, 'Isometrico'),
    ('Russian Twist', MuscleGroup.ABS, ''),
    ('Leg Raise', MuscleGroup.ABS, ''),

    # Polpacci
    ('Calf Raise in Piedi', MuscleGroup.CALVES, ''),
    ('Calf Raise Seduto', MuscleGroup.CALVES, ''),
]


class Command(BaseCommand):
    help = 'Popola il database con esercizi comuni'

    def handle(self, *args, **options):
        created = 0
        skipped = 0
        for name, muscle_group, description in EXERCISES:
            _, was_created = Exercise.objects.get_or_create(
                name=name,
                defaults={
                    'muscle_group': muscle_group,
                    'description': description,
                }
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Completato: {created} esercizi creati, {skipped} già esistenti.'
            )
        )
