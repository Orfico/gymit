import logging

from django import forms

from . import youtube
from .models import WorkoutPlan, PlannedExercise, ExerciseLog, Exercise, PlanFolder

logger = logging.getLogger(__name__)


class WorkoutPlanForm(forms.ModelForm):
    class Meta:
        model = WorkoutPlan
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'es. Push Pull Legs'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Note opzionali sulla scheda...'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PlanFolderForm(forms.ModelForm):
    class Meta:
        model = PlanFolder
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'es. Forza'
            }),
        }


class PlannedExerciseForm(forms.ModelForm):
    class Meta:
        model = PlannedExercise
        # 'order' escluso: viene assegnato automaticamente e gestito via drag & drop
        fields = ['exercise', 'target_sets', 'target_reps', 'notes']
        widgets = {
            'exercise': forms.Select(attrs={'class': 'form-select'}),
            'target_sets': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1, 'max': 20
            }),
            'target_reps': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1, 'max': 100
            }),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'es. Pausa 90s tra le serie'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['exercise'].queryset = Exercise.objects.all()


class PlannedExerciseEditForm(forms.ModelForm):
    """
    Modifica di un esercizio già in scheda.

    L'esercizio in sé non è modificabile: cambiarlo equivale a toglierne uno
    e aggiungerne un altro, e si scontrerebbe col vincolo di unicità
    (plan, exercise). Qui si aggiusta l'obiettivo — serie, ripetizioni, note.
    """
    class Meta:
        model = PlannedExercise
        fields = ['target_sets', 'target_reps', 'notes']
        widgets = {
            'target_sets': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1, 'max': 20, 'inputmode': 'numeric',
            }),
            'target_reps': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1, 'max': 100, 'inputmode': 'numeric',
            }),
            'notes': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'es. Pausa 90s tra le serie',
            }),
        }


class ExerciseLogForm(forms.ModelForm):
    class Meta:
        model = ExerciseLog
        fields = ['exercise', 'date', 'sets', 'reps', 'weight', 'notes']
        widgets = {
            'exercise': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(format='%Y-%m-%d', attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'sets': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1, 'max': 20
            }),
            'reps': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1, 'max': 100
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0, 'step': '0.5',
                'placeholder': 'kg'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Come è andata la sessione?'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['exercise'].queryset = Exercise.objects.all()
        self.fields['notes'].required = False
        self.fields['weight'].required = False

    def clean(self):
        cleaned_data = super().clean()
        exercise = cleaned_data.get('exercise')
        if exercise and exercise.is_bodyweight:
            cleaned_data['weight'] = None
        elif exercise and cleaned_data.get('weight') is None:
            self.add_error('weight', 'Il carico è obbligatorio per gli esercizi con pesi.')
        return cleaned_data


class ExerciseForm(forms.ModelForm):
    """Permette all'utente di aggiungere esercizi personalizzati."""
    class Meta:
        model = Exercise
        fields = ['name', 'muscle_group', 'description', 'is_bodyweight']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'es. Panca Inclinata con Manubri'
            }),
            'muscle_group': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descrizione tecnica opzionale...'
            }),
            'is_bodyweight': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }



class ExerciseVideoForm(forms.Form):
    """
    Accetta un URL YouTube in qualunque formato e ne ricava l'id.

    Dopo `is_valid()` l'id sta in `self.video_id`: la vista salva quello, mai
    il testo incollato.
    """

    url = forms.CharField(
        label='Link YouTube',
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://www.youtube.com/watch?v=...',
            'autocomplete': 'off',
            'inputmode': 'url',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.video_id = None

    def clean_url(self):
        raw_url = self.cleaned_data['url']

        video_id = youtube.extract_video_id(raw_url)
        if video_id is None:
            raise forms.ValidationError(
                'Link non valido. Incolla un indirizzo YouTube, per esempio '
                'https://www.youtube.com/watch?v=... oppure https://youtu.be/...'
            )

        exists = youtube.video_exists(video_id)
        if exists is False:
            raise forms.ValidationError(
                'Video non trovato su YouTube: potrebbe essere stato rimosso '
                'o non essere pubblico.'
            )
        if exists is None:
            # Controllo non riuscito: si salva comunque, ma resta traccia nei
            # log. Bloccare l'admin per un problema di rete sarebbe peggio.
            logger.warning(
                'Video %s salvato senza conferma: verifica non riuscita.', video_id
            )

        self.video_id = video_id
        return raw_url
