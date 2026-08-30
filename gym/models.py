from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

from . import youtube


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
    is_bodyweight = models.BooleanField(default=False, verbose_name='A corpo libero')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='custom_exercises'
    )

    # Video tutorial: un solo video per esercizio, sostituibile dagli admin.
    # Si salva l'identificativo, non l'URL incollato: gli indirizzi usati nel
    # markup vengono ricostruiti dalle proprietà qui sotto, così l'input
    # dell'utente non può finire in un attributo `src`.
    youtube_video_id = models.CharField(
        max_length=11, null=True, blank=True, verbose_name='ID video YouTube'
    )
    video_added_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='added_exercise_videos',
        verbose_name='Video aggiunto da'
    )
    video_added_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Video aggiunto il'
    )

    class Meta:
        ordering = ['muscle_group', 'name']
        verbose_name = 'Esercizio'
        verbose_name_plural = 'Esercizi'

    def __str__(self):
        return self.name

    @property
    def has_video(self):
        return bool(self.youtube_video_id)

    @property
    def video_thumbnail_url(self):
        return youtube.thumbnail_url(self.youtube_video_id) if self.youtube_video_id else ''

    @property
    def video_embed_url(self):
        return youtube.embed_url(self.youtube_video_id) if self.youtube_video_id else ''

    @property
    def video_watch_url(self):
        return youtube.watch_url(self.youtube_video_id) if self.youtube_video_id else ''


class PlanFolder(models.Model):
    """
    Cartella creata dall'utente per raggruppare le proprie schede.
    Un solo livello: una cartella contiene schede, non altre cartelle.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plan_folders')
    name = models.CharField(max_length=100, verbose_name='Nome cartella')
    order = models.PositiveIntegerField(default=0, verbose_name='Ordine')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = 'Cartella'
        verbose_name_plural = 'Cartelle'

    def __str__(self):
        return f"{self.name} ({self.user.username})"


class WorkoutPlan(models.Model):
    """Scheda d'allenamento dell'utente."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='plans')
    name = models.CharField(max_length=100, verbose_name='Nome scheda')
    description = models.TextField(blank=True, verbose_name='Note')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, verbose_name='Attiva')
    order = models.PositiveIntegerField(default=0, verbose_name='Ordine')
    folder = models.ForeignKey(
        PlanFolder,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='plans',
        verbose_name='Cartella',
    )

    class Meta:
        ordering = ['order', '-created_at']
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
        validators=[MinValueValidator(0)],
        null=True, blank=True,
    )
    one_rm = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        editable=False,
        null=True,
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
        if self.exercise.is_bodyweight:
            self.weight = None
            self.one_rm = None
        else:
            self.one_rm = self.epley(self.weight, self.reps)
        super().save(*args, **kwargs)

    def __str__(self):
        if self.exercise.is_bodyweight:
            return f"{self.exercise.name} — {self.date} — {self.sets}x{self.reps}"
        return (
            f"{self.exercise.name} — {self.date} — "
            f"{self.weight}kg × {self.sets}x{self.reps} "
            f"(1RM: {self.one_rm}kg)"
        )


class WorkoutSession(models.Model):
    """
    Giornata di allenamento effettuata dall'utente.

    Registra CHE l'utente si è allenato e con quale scheda — è il diario
    delle presenze, distinto da ExerciseLog che registra i carichi.

    `plan` è opzionale e con SET_NULL, mentre `plan_name` è denormalizzato
    e sempre valorizzato: lo storico deve sopravvivere alla cancellazione
    di una scheda, e l'import CSV può contenere schede mai esistite in app.

    `is_free` marca gli allenamenti descritti a mano (es. "Cardio"), che non
    corrispondono a nessuna scheda. Serve un flag esplicito perché `plan`
    nullo da solo non basta a distinguerli: ce l'hanno anche le sessioni
    importate da CSV con schede sconosciute o poi eliminate.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='workout_sessions'
    )
    date = models.DateField(verbose_name='Data')
    plan = models.ForeignKey(
        WorkoutPlan,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sessions',
        verbose_name='Scheda'
    )
    plan_name = models.CharField(max_length=100, verbose_name='Nome scheda')
    is_free = models.BooleanField(default=False, verbose_name='Allenamento libero')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        verbose_name = 'Sessione di allenamento'
        verbose_name_plural = 'Sessioni di allenamento'
        indexes = [
            models.Index(fields=['user', '-date']),
        ]
        constraints = [
            # Una stessa scheda non può essere registrata due volte nello
            # stesso giorno; giorni con più schede diverse sono permessi.
            models.UniqueConstraint(
                fields=['user', 'date', 'plan_name'],
                name='unique_session_per_plan_per_day',
            ),
        ]

    def save(self, *args, **kwargs):
        # plan_name segue sempre la scheda collegata, se c'è.
        if self.plan and not self.plan_name:
            self.plan_name = self.plan.name
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.date} — {self.plan_name} ({self.user.username})"
