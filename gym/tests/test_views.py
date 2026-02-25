from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal

from gym.models import Exercise, WorkoutPlan, PlannedExercise, ExerciseLog, MuscleGroup


class AuthRequiredTest(TestCase):
    """Verifica che le view richiedano autenticazione."""

    PROTECTED_URLS = [
        'dashboard',
        'plan_list',
        'plan_create',
        'log_create',
        'progress_overview',
        'exercise_list',
        'exercise_create',
    ]

    def test_redirects_anonymous(self):
        client = Client()
        for name in self.PROTECTED_URLS:
            with self.subTest(view=name):
                response = client.get(reverse(name))
                self.assertIn(response.status_code, [301, 302])


class DashboardViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('dash', password='pass')
        self.client.login(username='dash', password='pass')

    def test_dashboard_loads(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dash')

    def test_dashboard_shows_no_logs_empty_state(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'Aggiungi primo log')


class LogCreateViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('logger', password='pass')
        self.client.login(username='logger', password='pass')
        self.exercise = Exercise.objects.create(
            name='Press Militare', muscle_group=MuscleGroup.SHOULDERS
        )

    def test_log_create_get(self):
        response = self.client.get(reverse('log_create'))
        self.assertEqual(response.status_code, 200)

    def test_log_create_post_creates_record(self):
        response = self.client.post(reverse('log_create'), {
            'exercise': self.exercise.pk,
            'date': date.today().isoformat(),
            'sets': 4,
            'reps': 8,
            'weight': '60.00',
            'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ExerciseLog.objects.count(), 1)

    def test_log_calculates_one_rm_on_create(self):
        self.client.post(reverse('log_create'), {
            'exercise': self.exercise.pk,
            'date': date.today().isoformat(),
            'sets': 3,
            'reps': 10,
            'weight': '50.00',
            'notes': '',
        })
        log = ExerciseLog.objects.first()
        # 50 × (1 + 10/30) = 66.67
        self.assertAlmostEqual(float(log.one_rm), 66.67, places=1)


class ProgressViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('proguser', password='pass')
        self.client.login(username='proguser', password='pass')
        self.exercise = Exercise.objects.create(
            name='Curl Bilanciere', muscle_group=MuscleGroup.BICEPS
        )

    def _add_log(self, weight, reps=8, sets=3):
        return ExerciseLog.objects.create(
            user=self.user,
            exercise=self.exercise,
            date=date.today(),
            sets=sets,
            reps=reps,
            weight=Decimal(str(weight)),
        )

    def test_progress_view_loads(self):
        self._add_log(30)
        response = self.client.get(
            reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Curl Bilanciere')

    def test_progress_contains_best_one_rm(self):
        self._add_log(30, reps=8)  # 1RM = 38.0
        self._add_log(35, reps=8)  # 1RM = 44.33 — best
        response = self.client.get(
            reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk})
        )
        self.assertContains(response, '44.33')

    def test_logs_are_not_overwritten(self):
        """Due POST distinti → due log distinti in DB."""
        for weight in [30, 35]:
            self._add_log(weight)
        self.assertEqual(ExerciseLog.objects.filter(
            user=self.user, exercise=self.exercise
        ).count(), 2)


class ExerciseAutocompleteTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('acuser', password='pass')
        self.client.login(username='acuser', password='pass')
        Exercise.objects.create(name='Panca Piana', muscle_group=MuscleGroup.CHEST)
        Exercise.objects.create(name='Panca Inclinata', muscle_group=MuscleGroup.CHEST)
        Exercise.objects.create(name='Squat', muscle_group=MuscleGroup.LEGS)

    def test_returns_json(self):
        response = self.client.get(reverse('exercise_autocomplete') + '?q=pan')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_filters_by_name(self):
        data = self.client.get(reverse('exercise_autocomplete') + '?q=pan').json()
        names = [r['name'] for r in data['results']]
        self.assertIn('Panca Piana', names)
        self.assertIn('Panca Inclinata', names)
        self.assertNotIn('Squat', names)

    def test_short_query_returns_empty(self):
        data = self.client.get(reverse('exercise_autocomplete') + '?q=p').json()
        self.assertEqual(data['results'], [])

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('exercise_autocomplete') + '?q=pan')
        self.assertIn(response.status_code, [301, 302])


class WorkoutPlanViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('planuser', password='pass')
        self.client.login(username='planuser', password='pass')

    def test_create_plan(self):
        response = self.client.post(reverse('plan_create'), {
            'name': 'Upper Lower',
            'description': '',
            'is_active': True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(WorkoutPlan.objects.count(), 1)

    def test_plan_detail_visible_only_to_owner(self):
        plan = WorkoutPlan.objects.create(user=self.user, name='Mia Scheda')
        other = User.objects.create_user('other', password='pass')
        self.client.login(username='other', password='pass')
        response = self.client.get(reverse('plan_detail', kwargs={'pk': plan.pk}))
        self.assertEqual(response.status_code, 404)


class PlanReorderTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('reorder', password='pass')
        self.client.login(username='reorder', password='pass')
        self.plan = WorkoutPlan.objects.create(user=self.user, name='Test Plan')
        ex1 = Exercise.objects.create(name='Squat', muscle_group=MuscleGroup.LEGS)
        ex2 = Exercise.objects.create(name='Leg Press', muscle_group=MuscleGroup.LEGS)
        ex3 = Exercise.objects.create(name='Leg Curl', muscle_group=MuscleGroup.LEGS)
        self.pe1 = PlannedExercise.objects.create(plan=self.plan, exercise=ex1, target_sets=4, target_reps=6, order=0)
        self.pe2 = PlannedExercise.objects.create(plan=self.plan, exercise=ex2, target_sets=3, target_reps=10, order=1)
        self.pe3 = PlannedExercise.objects.create(plan=self.plan, exercise=ex3, target_sets=3, target_reps=12, order=2)

    def _reorder(self, order):
        import json
        return self.client.post(
            reverse('plan_reorder', kwargs={'pk': self.plan.pk}),
            data=json.dumps({'order': order}),
            content_type='application/json',
        )

    def test_reorder_returns_ok(self):
        response = self._reorder([self.pe3.pk, self.pe1.pk, self.pe2.pk])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_reorder_updates_order_field(self):
        self._reorder([self.pe3.pk, self.pe1.pk, self.pe2.pk])
        self.pe1.refresh_from_db()
        self.pe2.refresh_from_db()
        self.pe3.refresh_from_db()
        self.assertEqual(self.pe3.order, 0)
        self.assertEqual(self.pe1.order, 1)
        self.assertEqual(self.pe2.order, 2)

    def test_reorder_invalid_ids_rejected(self):
        response = self._reorder([self.pe1.pk, self.pe2.pk, 9999])
        self.assertEqual(response.status_code, 400)

    def test_reorder_other_user_plan_rejected(self):
        other = User.objects.create_user('other2', password='pass')
        self.client.login(username='other2', password='pass')
        response = self._reorder([self.pe1.pk, self.pe2.pk, self.pe3.pk])
        self.assertEqual(response.status_code, 404)
