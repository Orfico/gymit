import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.messages.storage.cookie import CookieStorage
from django.http import HttpResponse
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User

from gym.models import Exercise, WorkoutPlan, PlannedExercise, ExerciseLog, MuscleGroup
from gym.views import log_create as log_create_view


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_user(username='testuser', password='testpass'):
    return User.objects.create_user(username, password=password)

def make_exercise(name='Squat', muscle=MuscleGroup.LEGS):
    return Exercise.objects.create(name=name, muscle_group=muscle)

def make_plan(user, name='Test Plan', is_active=True, order=0):
    return WorkoutPlan.objects.create(user=user, name=name, is_active=is_active, order=order)

def make_log(user, exercise, weight=100, reps=5, sets=3, log_date=None):
    return ExerciseLog.objects.create(
        user=user, exercise=exercise,
        date=log_date or date.today(),
        sets=sets, reps=reps,
        weight=Decimal(str(weight)),
    )


# ─── Auth ─────────────────────────────────────────────────────────────────────

class AuthRequiredTest(TestCase):
    PROTECTED = [
        'dashboard', 'plan_list', 'plan_create',
        'log_create', 'progress_overview', 'exercise_list',
        'exercise_create', 'plan_import',
    ]

    def test_redirects_anonymous(self):
        client = Client()
        for name in self.PROTECTED:
            with self.subTest(view=name):
                r = client.get(reverse(name))
                self.assertIn(r.status_code, [301, 302])


# ─── Dashboard ────────────────────────────────────────────────────────────────

class DashboardTest(TestCase):
    def setUp(self):
        self.user = make_user('dash')
        self.client.login(username='dash', password='testpass')

    def test_loads(self):
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.status_code, 200)

    def test_empty_state(self):
        r = self.client.get(reverse('dashboard'))
        self.assertContains(r, 'Aggiungi primo log')


# ─── Log CRUD ─────────────────────────────────────────────────────────────────

class LogCreateTest(TestCase):
    def setUp(self):
        self.user = make_user('logger')
        self.client.login(username='logger', password='testpass')
        self.exercise = make_exercise('Panca Piana', MuscleGroup.CHEST)

    def _post(self, **kwargs):
        data = {
            'exercise': self.exercise.pk,
            'date': date.today().isoformat(),
            'sets': 3, 'reps': 8, 'weight': '80.00', 'notes': '',
        }
        data.update(kwargs)
        return self.client.post(reverse('log_create'), data)

    def test_creates_log(self):
        self._post()
        self.assertEqual(ExerciseLog.objects.count(), 1)

    def test_calculates_one_rm(self):
        self._post(weight='100.00', reps=10)
        log = ExerciseLog.objects.first()
        self.assertAlmostEqual(float(log.one_rm), 133.33, places=1)

    def test_redirects_to_progress(self):
        r = self._post()
        self.assertRedirects(
            r,
            reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk}),
            fetch_redirect_response=False,
        )

    def test_redirects_to_plan_if_from_param(self):
        plan = make_plan(self.user)
        r = self.client.post(
            reverse('log_create'),
            {
                'exercise': self.exercise.pk,
                'date': date.today().isoformat(),
                'sets': 3, 'reps': 8, 'weight': '80.00',
                'notes': '', 'from': 'plan', 'plan': plan.pk,
            }
        )
        self.assertRedirects(
            r,
            reverse('plan_detail', kwargs={'pk': plan.pk}),
            fetch_redirect_response=False,
        )

    def _get_log_form_initial(self, params):
        factory = RequestFactory()
        request = factory.get(reverse('log_create'), params)
        request.user = self.user
        request._messages = CookieStorage(request)
        ctx = {}
        with patch('gym.views.render', side_effect=lambda _req, _tpl, context, **_kw: (ctx.update(context) or HttpResponse(''))):
            log_create_view(request)
        return ctx['form'].initial

    def test_prefills_sets_reps_from_plan(self):
        plan = make_plan(self.user)
        PlannedExercise.objects.create(
            plan=plan, exercise=self.exercise, target_sets=4, target_reps=6, order=0
        )
        initial = self._get_log_form_initial(
            {'exercise': self.exercise.pk, 'from': 'plan', 'plan': plan.pk}
        )
        self.assertEqual(initial.get('sets'), 4)
        self.assertEqual(initial.get('reps'), 6)

    def test_prefill_not_applied_without_plan_context(self):
        plan = make_plan(self.user)
        PlannedExercise.objects.create(
            plan=plan, exercise=self.exercise, target_sets=4, target_reps=6, order=0
        )
        initial = self._get_log_form_initial({'exercise': self.exercise.pk})
        self.assertNotIn('sets', initial)
        self.assertNotIn('reps', initial)

    def test_historic_immutability(self):
        self._post(weight='80.00')
        self._post(weight='85.00')
        self.assertEqual(ExerciseLog.objects.count(), 2)


class LogEditTest(TestCase):
    def setUp(self):
        self.user = make_user('editor')
        self.client.login(username='editor', password='testpass')
        self.exercise = make_exercise('Deadlift', MuscleGroup.BACK)
        self.log = make_log(self.user, self.exercise, weight=100, reps=5)

    def test_edit_page_loads(self):
        r = self.client.get(reverse('log_edit', kwargs={'pk': self.log.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Modifica sessione')

    def test_edit_updates_log(self):
        self.client.post(reverse('log_edit', kwargs={'pk': self.log.pk}), {
            'exercise': self.exercise.pk,
            'date': date.today().isoformat(),
            'sets': 4, 'reps': 6, 'weight': '110.00', 'notes': '',
        })
        self.log.refresh_from_db()
        self.assertEqual(float(self.log.weight), 110.0)
        self.assertEqual(self.log.sets, 4)

    def test_edit_recalculates_one_rm(self):
        self.client.post(reverse('log_edit', kwargs={'pk': self.log.pk}), {
            'exercise': self.exercise.pk,
            'date': date.today().isoformat(),
            'sets': 3, 'reps': 10, 'weight': '100.00', 'notes': '',
        })
        self.log.refresh_from_db()
        self.assertAlmostEqual(float(self.log.one_rm), 133.33, places=1)

    def test_other_user_cannot_edit(self):
        other = make_user('other')
        self.client.login(username='other', password='testpass')
        r = self.client.get(reverse('log_edit', kwargs={'pk': self.log.pk}))
        self.assertEqual(r.status_code, 404)


class LogDeleteTest(TestCase):
    def setUp(self):
        self.user = make_user('deleter')
        self.client.login(username='deleter', password='testpass')
        self.exercise = make_exercise('Curl', MuscleGroup.BICEPS)
        self.log = make_log(self.user, self.exercise)

    def test_delete_removes_log(self):
        self.client.post(reverse('log_delete', kwargs={'pk': self.log.pk}))
        self.assertEqual(ExerciseLog.objects.count(), 0)

    def test_other_user_cannot_delete(self):
        other = make_user('other2')
        self.client.login(username='other2', password='testpass')
        self.client.post(reverse('log_delete', kwargs={'pk': self.log.pk}))
        self.assertEqual(ExerciseLog.objects.count(), 1)


# ─── Progress ─────────────────────────────────────────────────────────────────

class ProgressViewTest(TestCase):
    def setUp(self):
        self.user = make_user('prog')
        self.client.login(username='prog', password='testpass')
        self.exercise = make_exercise('Press', MuscleGroup.SHOULDERS)

    def test_loads(self):
        make_log(self.user, self.exercise)
        r = self.client.get(reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk}))
        self.assertEqual(r.status_code, 200)

    def test_best_one_rm_is_alltime(self):
        make_log(self.user, self.exercise, weight=80, reps=8)
        make_log(self.user, self.exercise, weight=90, reps=8)
        r = self.client.get(reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk}))
        self.assertGreater(float(r.context['best_one_rm']), 90)

    def test_period_filter_1y(self):
        from datetime import timedelta
        old_date = date.today() - timedelta(days=400)
        make_log(self.user, self.exercise, log_date=old_date)
        make_log(self.user, self.exercise)
        r = self.client.get(
            reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk}) + '?period=1y'
        )
        self.assertEqual(r.context['log_count'], 1)

    def test_period_filter_all(self):
        from datetime import timedelta
        old_date = date.today() - timedelta(days=400)
        make_log(self.user, self.exercise, log_date=old_date)
        make_log(self.user, self.exercise)
        r = self.client.get(
            reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk}) + '?period=all'
        )
        self.assertEqual(r.context['log_count'], 2)


class ProgressOverviewTest(TestCase):
    def setUp(self):
        self.user = make_user('overview')
        self.client.login(username='overview', password='testpass')

    def test_no_duplicates(self):
        ex = make_exercise('Squat2', MuscleGroup.LEGS)
        make_log(self.user, ex, weight=100)
        make_log(self.user, ex, weight=110)
        r = self.client.get(reverse('progress_overview'))
        self.assertEqual(len(r.context['exercises']), 1)

    def test_shows_only_own_exercises(self):
        other = make_user('other3')
        ex = make_exercise('Leg Press', MuscleGroup.LEGS)
        make_log(other, ex)
        r = self.client.get(reverse('progress_overview'))
        self.assertEqual(len(r.context['exercises']), 0)


# ─── Workout Plans ────────────────────────────────────────────────────────────

class WorkoutPlanTest(TestCase):
    def setUp(self):
        self.user = make_user('planner')
        self.client.login(username='planner', password='testpass')

    def test_create_plan(self):
        self.client.post(reverse('plan_create'), {
            'name': 'PPL', 'description': '', 'is_active': True,
        })
        self.assertEqual(WorkoutPlan.objects.count(), 1)

    def test_create_auto_assigns_order(self):
        self.client.post(reverse('plan_create'), {'name': 'A', 'is_active': True})
        self.client.post(reverse('plan_create'), {'name': 'B', 'is_active': True})
        orders = list(WorkoutPlan.objects.order_by('order').values_list('order', flat=True))
        self.assertEqual(orders[0] < orders[1], True)

    def test_detail_requires_ownership(self):
        plan = make_plan(self.user)
        other = make_user('other4')
        self.client.login(username='other4', password='testpass')
        r = self.client.get(reverse('plan_detail', kwargs={'pk': plan.pk}))
        self.assertEqual(r.status_code, 404)

    def test_plan_list_separates_active_archived(self):
        make_plan(self.user, 'Attiva', is_active=True)
        make_plan(self.user, 'Archiviata', is_active=False)
        r = self.client.get(reverse('plan_list'))
        self.assertEqual(len(r.context['active_plans']), 1)
        self.assertEqual(len(r.context['archived_plans']), 1)


class PlanReorderTest(TestCase):
    def setUp(self):
        self.user = make_user('reorder')
        self.client.login(username='reorder', password='testpass')
        self.plan = make_plan(self.user)
        ex1 = make_exercise('Ex1', MuscleGroup.CHEST)
        ex2 = make_exercise('Ex2', MuscleGroup.BACK)
        ex3 = make_exercise('Ex3', MuscleGroup.LEGS)
        self.pe1 = PlannedExercise.objects.create(plan=self.plan, exercise=ex1, target_sets=3, target_reps=8, order=0)
        self.pe2 = PlannedExercise.objects.create(plan=self.plan, exercise=ex2, target_sets=3, target_reps=8, order=1)
        self.pe3 = PlannedExercise.objects.create(plan=self.plan, exercise=ex3, target_sets=3, target_reps=8, order=2)

    def _reorder(self, order):
        return self.client.post(
            reverse('plan_reorder', kwargs={'pk': self.plan.pk}),
            data=json.dumps({'order': order}),
            content_type='application/json',
        )

    def test_reorder_ok(self):
        r = self._reorder([self.pe3.pk, self.pe1.pk, self.pe2.pk])
        self.assertEqual(r.json()['status'], 'ok')

    def test_reorder_updates_order(self):
        self._reorder([self.pe3.pk, self.pe1.pk, self.pe2.pk])
        self.pe3.refresh_from_db()
        self.assertEqual(self.pe3.order, 0)

    def test_invalid_ids_rejected(self):
        r = self._reorder([self.pe1.pk, self.pe2.pk, 9999])
        self.assertEqual(r.status_code, 400)

    def test_other_user_rejected(self):
        other = make_user('other5')
        self.client.login(username='other5', password='testpass')
        r = self._reorder([self.pe1.pk, self.pe2.pk, self.pe3.pk])
        self.assertEqual(r.status_code, 404)


# ─── Export / Import ──────────────────────────────────────────────────────────

class PlanExportTest(TestCase):
    def setUp(self):
        self.user = make_user('exporter')
        self.client.login(username='exporter', password='testpass')
        self.plan = make_plan(self.user, 'Push Day')
        ex = make_exercise('Panca', MuscleGroup.CHEST)
        PlannedExercise.objects.create(
            plan=self.plan, exercise=ex,
            target_sets=4, target_reps=8, order=0
        )

    def test_export_returns_csv(self):
        r = self.client.get(reverse('plan_export', kwargs={'pk': self.plan.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])

    def test_export_contains_plan_name(self):
        r = self.client.get(reverse('plan_export', kwargs={'pk': self.plan.pk}))
        content = b''.join(r.streaming_content).decode('utf-8-sig') if hasattr(r, 'streaming_content') else r.content.decode('utf-8-sig')
        self.assertIn('Push Day', content)

    def test_export_contains_exercise(self):
        r = self.client.get(reverse('plan_export', kwargs={'pk': self.plan.pk}))
        content = r.content.decode('utf-8-sig')
        self.assertIn('Panca', content)

    def test_other_user_cannot_export(self):
        other = make_user('other6')
        self.client.login(username='other6', password='testpass')
        r = self.client.get(reverse('plan_export', kwargs={'pk': self.plan.pk}))
        self.assertEqual(r.status_code, 404)


class PlanImportTest(TestCase):
    def setUp(self):
        self.user = make_user('importer')
        self.client.login(username='importer', password='testpass')

    def _make_csv(self, plan_name='Imported Plan', rows=None):
        import io
        if rows is None:
            rows = [['Squat', 'legs', '4', '6', '0', '']]
        content = f'piano,{plan_name},\r\nesercizio,gruppo_muscolare,serie,ripetizioni,ordine,note\r\n'
        for row in rows:
            content += ','.join(row) + '\r\n'
        return io.BytesIO(content.encode('utf-8-sig'))

    def test_import_creates_plan(self):
        csv_file = self._make_csv()
        csv_file.name = 'test.csv'
        self.client.post(reverse('plan_import'), {'csv_file': csv_file})
        self.assertEqual(WorkoutPlan.objects.filter(user=self.user).count(), 1)

    def test_import_creates_missing_exercise(self):
        csv_file = self._make_csv(rows=[['Nuovo Esercizio', 'chest', '3', '10', '0', '']])
        csv_file.name = 'test.csv'
        self.client.post(reverse('plan_import'), {'csv_file': csv_file})
        self.assertTrue(Exercise.objects.filter(name='Nuovo Esercizio').exists())

    def test_import_reuses_existing_exercise(self):
        make_exercise('Squat', MuscleGroup.LEGS)
        csv_file = self._make_csv()
        csv_file.name = 'test.csv'
        self.client.post(reverse('plan_import'), {'csv_file': csv_file})
        self.assertEqual(Exercise.objects.filter(name='Squat').count(), 1)

    def test_import_wrong_extension_rejected(self):
        import io
        f = io.BytesIO(b'data')
        f.name = 'test.txt'
        r = self.client.post(reverse('plan_import'), {'csv_file': f})
        self.assertContains(r, 'formato CSV')

    def test_import_invalid_format_rejected(self):
        import io
        f = io.BytesIO(b'questo,non,e,un,csv,valido\n')
        f.name = 'test.csv'
        r = self.client.post(reverse('plan_import'), {'csv_file': f})
        self.assertContains(r, 'non valido')

    def test_import_get_shows_form(self):
        r = self.client.get(reverse('plan_import'))
        self.assertEqual(r.status_code, 200)


# ─── Autocomplete ─────────────────────────────────────────────────────────────

class AutocompleteTest(TestCase):
    def setUp(self):
        self.user = make_user('ac')
        self.client.login(username='ac', password='testpass')
        make_exercise('Panca Piana', MuscleGroup.CHEST)
        make_exercise('Panca Inclinata', MuscleGroup.CHEST)
        make_exercise('Squat', MuscleGroup.LEGS)

    def test_filters_by_name(self):
        r = self.client.get(reverse('exercise_autocomplete') + '?q=pan')
        data = r.json()
        names = [x['name'] for x in data['results']]
        self.assertIn('Panca Piana', names)
        self.assertNotIn('Squat', names)

    def test_short_query_returns_empty(self):
        r = self.client.get(reverse('exercise_autocomplete') + '?q=p')
        self.assertEqual(r.json()['results'], [])

    def test_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse('exercise_autocomplete') + '?q=pan')
        self.assertIn(r.status_code, [301, 302])


# ─── Service Worker ───────────────────────────────────────────────────────────

class ServiceWorkerTest(TestCase):
    def test_sw_accessible(self):
        r = self.client.get('/sw.js')
        self.assertEqual(r.status_code, 200)
        self.assertIn('javascript', r['Content-Type'])

    def test_sw_no_cache_header(self):
        r = self.client.get('/sw.js')
        self.assertIn('no-cache', r['Cache-Control'])

    def test_sw_allowed_header(self):
        r = self.client.get('/sw.js')
        self.assertEqual(r['Service-Worker-Allowed'], '/')