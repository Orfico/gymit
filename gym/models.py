from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator


class MuscleGroup(models.TextChoices):
    CHEST = 'chest', 'Petto'
    BACK = 'back', 'Schiena'
    SHOULDERS = 'shoulders', 'Spalle'
    BICEPS = 'biceps', 'Bicipiti'
    TRICEPS = 'triceps', 'Tricipiti'
    LEGS = 'legs', 'Gambe'
    GLUTES = 'glutes', 'Glutei'
    ABS = 'abs', 'Addome'
    CALVES = 'calves', 'Polpacci'
    FOREARMS = 'forearms', 'Avambracci'
    FULL_BODY = 'full_body', 'Full Body'


class Exercise(models.Model):
    """Catalogo degli esercizi (globale + creati dall'utente)."""
    name = models.CharField(max_length=100, unique=True, verbose_name='Nome')
    muscle_group = models.CharField(
        max_length=20,
        choices=MuscleGroup.choices,
        verbose_name='Gruppo muscolare'
    )
    description = models.TextField(blank=True, verbose_name='Descrizione')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='custom_exercises'
    )

    class Meta:
        ordering = ['muscle_group', 'name']
        verbose_name = 'Esercizio'
        verbose_name_plural = 'Esercizi'

    def __str__(self):
        return self.name


class WorkoutPlan(models.Model):
    """Scheda d'allenamento dell'utente."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plans')
    name = models.CharField(max_length=100, verbose_name='Nome scheda')
    description = models.TextField(blank=True, verbose_name='Note')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, verbose_name='Attiva')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Scheda'
        verbose_name_plural = 'Schede'

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class PlannedExercise(models.Model):
    """
    Esercizio pianificato all'interno di una scheda.
    Definisce l'obiettivo: quante serie e ripetizioni fare.
    """
    plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.CASCADE,
        related_name='planned_exercises'
    )
    exercise = models.ForeignKey(Exercise, on_delete=models.CASCADE)
    target_sets = models.PositiveSmallIntegerField(
        verbose_name='Serie obiettivo',
        validators=[MinValueValidator(1)]
    )
    target_reps = models.PositiveSmallIntegerField(
        verbose_name='Ripetizioni obiettivo',
        validators=[MinValueValidator(1)]
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordine')
    notes = models.CharField(max_length=200, blank=True, verbose_name='Note')

    class Meta:
        ordering = ['order']
        unique_together = ('plan', 'exercise')
        verbose_name = 'Esercizio in scheda'
        verbose_name_plural = 'Esercizi in scheda'

    def __str__(self):
        return f"{self.exercise.name} — {self.target_sets}x{self.target_reps}"


class ExerciseLog(models.Model):
    """
    Registro di una singola sessione di un esercizio.

    Ogni modifica al carico produce un NUOVO record — lo storico è immutabile
    by design. Il carico corrente è sempre l'ultimo log per data.
    Il massimale teorico (1RM) viene calcolato con la formula di Epley
    al momento del salvataggio e persistito per efficienza nelle query.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='exercise_logs'
    )
    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    date = models.DateField(verbose_name='Data')
    sets = models.PositiveSmallIntegerField(
        verbose_name='Serie eseguite',
        validators=[MinValueValidator(1)]
    )
    reps = models.PositiveSmallIntegerField(
        verbose_name='Ripetizioni eseguite',
        validators=[MinValueValidator(1)]
    )
    weight = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        verbose_name='Carico (kg)',
        validators=[MinValueValidator(0)]
    )
    one_rm = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        editable=False,
        verbose_name='Massimale teorico (kg)'
    )
    notes = models.TextField(blank=True, verbose_name='Note sessione')

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = 'Log allenamento'
        verbose_name_plural = 'Log allenamenti'
        indexes = [
            models.Index(fields=['user', 'exercise', '-date']),
        ]

    @staticmethod
    def epley(weight: float, reps: int) -> float:
        """
        Formula di Epley: 1RM = weight × (1 + reps / 30)
        Accurata per range 1–15 ripetizioni.
        Per 1 ripetizione restituisce il peso stesso (corretto).
        """
        if reps == 1:
            return round(float(weight), 2)
        return round(float(weight) * (1 + reps / 30), 2)

    def save(self, *args, **kwargs):
        self.one_rm = self.epley(self.weight, self.reps)
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.exercise.name} — {self.date} — "
            f"{self.weight}kg × {self.sets}x{self.reps} "
            f"(1RM: {self.one_rm}kg)"
        )
