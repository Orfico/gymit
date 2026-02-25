from django.test import TestCase
from django.contrib.auth.models import User
from datetime import date

from gym.forms import ExerciseLogForm, WorkoutPlanForm, ExerciseForm
from gym.models import Exercise, MuscleGroup


class ExerciseLogFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('formuser', password='pass')
        self.exercise = Exercise.objects.create(
            name='Deadlift',
            muscle_group=MuscleGroup.BACK,
        )

    def _valid_data(self, **overrides):
        data = {
            'exercise': self.exercise.pk,
            'date': date.today().isoformat(),
            'sets': 3,
            'reps': 5,
            'weight': '100.00',
            'notes': '',
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = ExerciseLogForm(data=self._valid_data(), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_zero_weight_allowed(self):
        """Peso 0 è valido (es. esercizi a corpo libero)."""
        form = ExerciseLogForm(data=self._valid_data(weight='0'), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_negative_weight_invalid(self):
        form = ExerciseLogForm(data=self._valid_data(weight='-5'), user=self.user)
        self.assertFalse(form.is_valid())

    def test_zero_reps_invalid(self):
        form = ExerciseLogForm(data=self._valid_data(reps=0), user=self.user)
        self.assertFalse(form.is_valid())

    def test_missing_exercise_invalid(self):
        data = self._valid_data()
        del data['exercise']
        form = ExerciseLogForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())


class WorkoutPlanFormTest(TestCase):
    def test_valid_plan_form(self):
        form = WorkoutPlanForm(data={'name': 'My Plan', 'is_active': True})
        self.assertTrue(form.is_valid())

    def test_empty_name_invalid(self):
        form = WorkoutPlanForm(data={'name': '', 'is_active': True})
        self.assertFalse(form.is_valid())


class ExerciseFormTest(TestCase):
    def test_valid_exercise_form(self):
        form = ExerciseForm(data={
            'name': 'Trazioni',
            'muscle_group': MuscleGroup.BACK,
            'description': '',
        })
        self.assertTrue(form.is_valid())

    def test_duplicate_name(self):
        Exercise.objects.create(name='Trazioni', muscle_group=MuscleGroup.BACK)
        form = ExerciseForm(data={
            'name': 'Trazioni',
            'muscle_group': MuscleGroup.BACK,
        })
        self.assertFalse(form.is_valid())
