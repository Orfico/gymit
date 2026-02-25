from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date

from gym.models import Exercise, WorkoutPlan, PlannedExercise, ExerciseLog, MuscleGroup


class ExerciseLogOneRmTest(TestCase):
    """
    Verifica il calcolo del massimale teorico (formula Epley).
    Epley: 1RM = weight × (1 + reps / 30)
    """

    def setUp(self):
        self.user = User.objects.create_user('testuser', password='testpass')
        self.exercise = Exercise.objects.create(
            name='Panca Piana',
            muscle_group=MuscleGroup.CHEST,
        )

    def _make_log(self, weight, reps, sets=3):
        return ExerciseLog.objects.create(
            user=self.user,
            exercise=self.exercise,
            date=date.today(),
            sets=sets,
            reps=reps,
            weight=Decimal(str(weight)),
        )

    def test_epley_formula_standard(self):
        """100 kg × 10 reps → 1RM = 100 × (1 + 10/30) = 133.33"""
        log = self._make_log(weight=100, reps=10)
        self.assertAlmostEqual(float(log.one_rm), 133.33, places=1)

    def test_epley_single_rep(self):
        """1 ripetizione → il 1RM è il peso stesso."""
        log = self._make_log(weight=120, reps=1)
        self.assertEqual(float(log.one_rm), 120.0)

    def test_epley_5_reps(self):
        """80 kg × 5 reps → 1RM = 80 × (1 + 5/30) = 93.33"""
        log = self._make_log(weight=80, reps=5)
        self.assertAlmostEqual(float(log.one_rm), 93.33, places=1)

    def test_one_rm_auto_calculated_on_save(self):
        """Il campo one_rm viene popolato automaticamente al salvataggio."""
        log = self._make_log(weight=60, reps=12)
        self.assertIsNotNone(log.one_rm)
        self.assertGreater(float(log.one_rm), float(log.weight))

    def test_one_rm_not_editable(self):
        """Modifica diretta di one_rm deve essere sovrascritta al salvataggio."""
        log = self._make_log(weight=100, reps=10)
        log.one_rm = Decimal('999')
        log.save()
        log.refresh_from_db()
        self.assertNotEqual(float(log.one_rm), 999)

    def test_historic_immutability(self):
        """
        Ogni aggiornamento del carico crea un nuovo record,
        non sovrascrive quello precedente.
        """
        self._make_log(weight=80, reps=8)
        self._make_log(weight=85, reps=8)
        self._make_log(weight=90, reps=8)

        logs = ExerciseLog.objects.filter(user=self.user, exercise=self.exercise)
        self.assertEqual(logs.count(), 3)

        weights = list(logs.order_by('id').values_list('weight', flat=True))
        self.assertEqual([float(w) for w in weights], [80.0, 85.0, 90.0])

    def test_epley_static_method(self):
        """Test del metodo statico epley direttamente."""
        self.assertAlmostEqual(ExerciseLog.epley(100, 10), 133.33, places=1)
        self.assertEqual(ExerciseLog.epley(120, 1), 120.0)
        self.assertAlmostEqual(ExerciseLog.epley(60, 15), 90.0, places=1)


class WorkoutPlanTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('planuser', password='testpass')

    def test_plan_creation(self):
        plan = WorkoutPlan.objects.create(
            user=self.user,
            name='Push Pull Legs',
        )
        self.assertEqual(str(plan), 'Push Pull Legs (planuser)')
        self.assertTrue(plan.is_active)

    def test_planned_exercise_str(self):
        exercise = Exercise.objects.create(name='Squat', muscle_group=MuscleGroup.LEGS)
        plan = WorkoutPlan.objects.create(user=self.user, name='Scheda A')
        pe = PlannedExercise.objects.create(
            plan=plan, exercise=exercise, target_sets=4, target_reps=8
        )
        self.assertIn('Squat', str(pe))
        self.assertIn('4x8', str(pe))
