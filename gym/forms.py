from django import forms
from .models import WorkoutPlan, PlannedExercise, ExerciseLog, Exercise


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


class ExerciseLogForm(forms.ModelForm):
    class Meta:
        model = ExerciseLog
        fields = ['exercise', 'date', 'sets', 'reps', 'weight', 'notes']
        widgets = {
            'exercise': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={
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


class ExerciseForm(forms.ModelForm):
    """Permette all'utente di aggiungere esercizi personalizzati."""
    class Meta:
        model = Exercise
        fields = ['name', 'muscle_group', 'description']
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
        }
