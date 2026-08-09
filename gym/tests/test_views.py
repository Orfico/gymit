import io
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.messages.storage.cookie import CookieStorage
from django.http import HttpResponse
from django.test import TestCase, Client, RequestFactory
from django.urls import reverse
from django.contrib.auth.models import User

from django.utils import timezone

from gym.models import (
    Exercise, WorkoutPlan, PlannedExercise, ExerciseLog,
    MuscleGroup, PlanFolder, WorkoutSession,
)
from gym.views import log_create as log_create_view, dashboard as dashboard_view


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_user(username='testuser', password='testpass'):
    return User.objects.create_user(username, password=password)

def make_exercise(name='Squat', muscle=MuscleGroup.LEGS, is_bodyweight=False):
    return Exercise.objects.create(name=name, muscle_group=muscle, is_bodyweight=is_bodyweight)

def make_plan(user, name='Test Plan', is_active=True, order=0, folder=None):
    return WorkoutPlan.objects.create(user=user, name=name, is_active=is_active, order=order, folder=folder)

def make_folder(user, name='Cartella Test', order=0):
    return PlanFolder.objects.create(user=user, name=name, order=order)

def make_log(user, exercise, weight=100, reps=5, sets=3, log_date=None):
    return ExerciseLog.objects.create(
        user=user, exercise=exercise,
        date=log_date or date.today(),
        sets=sets, reps=reps,
        weight=Decimal(str(weight)) if weight is not None else None,
    )


# ─── Auth ─────────────────────────────────────────────────────────────────────

class AuthRequiredTest(TestCase):
    PROTECTED = [
        'dashboard', 'plan_list', 'plan_create',
        'log_create', 'progress_overview', 'exercise_list',
        'exercise_create', 'plan_import',
        'workout_calendar', 'session_import', 'session_create',
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
        self.factory = RequestFactory()

    def _ctx(self):
        request = self.factory.get(reverse('dashboard'))
        request.user = self.user
        request._messages = CookieStorage(request)
        ctx = {}
        with patch('gym.views.render', side_effect=lambda _r, _t, c, **_k: (ctx.update(c) or HttpResponse(''))):
            dashboard_view(request)
        return ctx

    def test_loads(self):
        ctx = self._ctx()
        self.assertIn('muscle_groups', ctx)

    def test_empty_state(self):
        self.assertEqual(self._ctx()['muscle_groups'], [])

    def test_muscle_group_shown_with_two_logs(self):
        ex = make_exercise('Panca DB', MuscleGroup.CHEST)
        make_log(self.user, ex, weight=80)
        make_log(self.user, ex, weight=90)
        ctx = self._ctx()
        keys = [mg['key'] for mg in ctx['muscle_groups']]
        self.assertIn('chest', keys)

    def test_muscle_group_hidden_with_one_log(self):
        ex = make_exercise('Curl Manubrio', MuscleGroup.BICEPS)
        make_log(self.user, ex)
        keys = [mg['key'] for mg in self._ctx()['muscle_groups']]
        self.assertNotIn('biceps', keys)

    def test_muscle_groups_ordered_by_total_logs(self):
        ex_chest = make_exercise('Panca Ord', MuscleGroup.CHEST)
        ex_legs = make_exercise('Squat Ord', MuscleGroup.LEGS)
        make_log(self.user, ex_chest, weight=80)
        make_log(self.user, ex_chest, weight=85)
        make_log(self.user, ex_legs, weight=100)
        make_log(self.user, ex_legs, weight=105)
        make_log(self.user, ex_legs, weight=110)
        keys = [mg['key'] for mg in self._ctx()['muscle_groups']]
        self.assertEqual(keys[0], 'legs')
        self.assertEqual(keys[1], 'chest')

    def test_stats_keys_present(self):
        ctx = self._ctx()
        for key in ('sessions_this_week', 'exercises_tracked', 'active_plans_count', 'greeting'):
            self.assertIn(key, ctx)

    def test_sessions_this_week_counts_only_current_week(self):
        ex = make_exercise('Stacco', MuscleGroup.BACK)
        make_log(self.user, ex, log_date=date.today())
        make_log(self.user, ex, log_date=date.today() - timedelta(weeks=2))
        self.assertEqual(self._ctx()['sessions_this_week'], 1)

    def test_exercises_tracked_counts_distinct_exercises_with_logs(self):
        ex_a = make_exercise('Panca Tracked', MuscleGroup.CHEST)
        ex_b = make_exercise('Curl Tracked', MuscleGroup.BICEPS)
        make_log(self.user, ex_a)
        make_log(self.user, ex_b)
        self.assertEqual(self._ctx()['exercises_tracked'], 2)

    def test_active_plans_count_excludes_archived(self):
        make_plan(self.user, name='Attiva', is_active=True)
        make_plan(self.user, name='Archiviata', is_active=False)
        self.assertEqual(self._ctx()['active_plans_count'], 1)

    def test_bodyweight_exercise_does_not_crash_dashboard(self):
        """
        one_rm è None per i log a corpo libero: l'aggregazione per gruppo
        muscolare deve saltarli, non andare in errore su float(None).
        """
        ex = make_exercise('Trazioni Dash', MuscleGroup.BACK, is_bodyweight=True)
        make_log(self.user, ex, weight=None, reps=10)
        make_log(self.user, ex, weight=None, reps=12)
        ctx = self._ctx()  # non deve sollevare eccezioni
        keys = [mg['key'] for mg in ctx['muscle_groups']]
        self.assertNotIn('back', keys)


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


class BodyweightProgressViewTest(TestCase):
    def setUp(self):
        self.user = make_user('bwprog')
        self.client.login(username='bwprog', password='testpass')
        self.exercise = make_exercise('Trazioni Prog', MuscleGroup.BACK, is_bodyweight=True)

    def test_loads_without_error(self):
        make_log(self.user, self.exercise, weight=None, reps=8)
        make_log(self.user, self.exercise, weight=None, reps=10)
        r = self.client.get(reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk}))
        self.assertEqual(r.status_code, 200)

    def test_best_reps_computed(self):
        make_log(self.user, self.exercise, weight=None, reps=8)
        make_log(self.user, self.exercise, weight=None, reps=15)
        r = self.client.get(reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk}))
        self.assertEqual(r.context['best_reps'], 15)
        self.assertIsNone(r.context['best_one_rm'])

    def test_chart_data_has_null_one_rm_and_weight(self):
        make_log(self.user, self.exercise, weight=None, reps=8)
        make_log(self.user, self.exercise, weight=None, reps=10)
        r = self.client.get(reverse('exercise_progress', kwargs={'exercise_id': self.exercise.pk}))
        chart_data = json.loads(r.context['chart_data'])
        self.assertTrue(all(entry['one_rm'] is None for entry in chart_data))
        self.assertTrue(all(entry['weight'] is None for entry in chart_data))
        self.assertTrue(all(entry['reps'] for entry in chart_data))


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

    def test_bodyweight_exercise_shows_best_reps(self):
        ex = make_exercise('Piegamenti Overview', MuscleGroup.CHEST, is_bodyweight=True)
        make_log(self.user, ex, weight=None, reps=12)
        make_log(self.user, ex, weight=None, reps=18)
        r = self.client.get(reverse('progress_overview'))
        item = next(i for i in r.context['exercises'] if i['exercise'].pk == ex.pk)
        self.assertEqual(item['best_reps'], 18)
        self.assertIsNone(item['best_one_rm'])


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
        self.assertEqual(len(r.context['root_nodes']), 1)
        self.assertEqual(r.context['root_nodes'][0]['type'], 'plan')
        self.assertEqual(len(r.context['archived_plans']), 1)

    def test_plan_list_root_nodes_include_folders(self):
        make_folder(self.user, 'Cartella')
        make_plan(self.user, 'Sciolta', is_active=True)
        r = self.client.get(reverse('plan_list'))
        types = sorted(n['type'] for n in r.context['root_nodes'])
        self.assertEqual(types, ['folder', 'plan'])

    def test_plan_list_plan_in_folder_not_at_root(self):
        folder = make_folder(self.user, 'Cartella')
        make_plan(self.user, 'Dentro', is_active=True, folder=folder)
        r = self.client.get(reverse('plan_list'))
        self.assertEqual(len(r.context['root_nodes']), 1)
        self.assertEqual(r.context['root_nodes'][0]['type'], 'folder')

    def test_has_active_plans_true_even_if_all_in_folders(self):
        folder = make_folder(self.user, 'Cartella')
        make_plan(self.user, 'Dentro', is_active=True, folder=folder)
        r = self.client.get(reverse('plan_list'))
        self.assertTrue(r.context['has_active_plans'])


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


class PlanListRootReorderTest(TestCase):
    """plan_list_reorder — riordino del livello radice (cartelle + schede sciolte)."""

    def setUp(self):
        self.user = make_user('rootreorder')
        self.client.login(username='rootreorder', password='testpass')

    def _reorder(self, order):
        return self.client.post(
            reverse('plan_list_reorder'),
            data=json.dumps({'order': order}),
            content_type='application/json',
        )

    def test_bug_regression_archived_plan_does_not_block_reorder(self):
        """
        Prima del fix: un utente con anche solo una scheda archiviata non
        poteva mai salvare il riordino delle schede attive, perché la vista
        pretendeva un payload con *tutte* le schede (comprese le
        archiviate), che il client non invia mai.
        """
        active = make_plan(self.user, 'Attiva', is_active=True)
        make_plan(self.user, 'Archiviata', is_active=False)
        r = self._reorder([{'type': 'plan', 'id': active.pk}])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'ok')

    def test_reorder_persists_after_reload(self):
        """Il caso concreto del bug: l'ordine deve sopravvivere a un nuovo GET."""
        p1 = make_plan(self.user, 'Prima', is_active=True, order=0)
        p2 = make_plan(self.user, 'Archiviata', is_active=False, order=1)
        p3 = make_plan(self.user, 'Seconda', is_active=True, order=2)
        self._reorder([{'type': 'plan', 'id': p3.pk}, {'type': 'plan', 'id': p1.pk}])
        r = self.client.get(reverse('plan_list'))
        ordered_ids = [n['obj'].pk for n in r.context['root_nodes']]
        self.assertEqual(ordered_ids, [p3.pk, p1.pk])

    def test_mixed_folder_and_plan_payload_updates_order(self):
        folder = make_folder(self.user, 'Cartella')
        plan = make_plan(self.user, 'Scheda', is_active=True)
        r = self._reorder([
            {'type': 'plan', 'id': plan.pk},
            {'type': 'folder', 'id': folder.pk},
        ])
        self.assertEqual(r.status_code, 200)
        plan.refresh_from_db()
        folder.refresh_from_db()
        self.assertEqual(plan.order, 0)
        self.assertEqual(folder.order, 1)

    def test_plan_included_here_gets_removed_from_folder(self):
        """Trascinare una scheda dalla cartella alla radice: folder -> None."""
        folder = make_folder(self.user, 'Cartella')
        plan = make_plan(self.user, 'Scheda', is_active=True, folder=folder)
        self._reorder([{'type': 'plan', 'id': plan.pk}])
        plan.refresh_from_db()
        self.assertIsNone(plan.folder)

    def test_partial_payload_is_not_an_error(self):
        """Diversamente dalla vecchia implementazione: niente equality-check."""
        p1 = make_plan(self.user, 'Uno', is_active=True)
        make_plan(self.user, 'Due', is_active=True)
        r = self._reorder([{'type': 'plan', 'id': p1.pk}])
        self.assertEqual(r.status_code, 200)

    def test_other_users_plan_rejected(self):
        other = make_user('rootother')
        other_plan = make_plan(other, 'Non mia', is_active=True)
        r = self._reorder([{'type': 'plan', 'id': other_plan.pk}])
        self.assertEqual(r.status_code, 400)

    def test_other_users_folder_rejected(self):
        other = make_user('rootother2')
        other_folder = make_folder(other, 'Non mia')
        r = self._reorder([{'type': 'folder', 'id': other_folder.pk}])
        self.assertEqual(r.status_code, 400)


class PlanFolderReorderTest(TestCase):
    """plan_folder_reorder — riordino/spostamento di schede dentro una cartella."""

    def setUp(self):
        self.user = make_user('folderreorder')
        self.client.login(username='folderreorder', password='testpass')
        self.folder = make_folder(self.user, 'Cartella')

    def _reorder(self, folder_pk, order):
        return self.client.post(
            reverse('plan_folder_reorder', kwargs={'pk': folder_pk}),
            data=json.dumps({'order': order}),
            content_type='application/json',
        )

    def test_moves_plan_into_folder(self):
        plan = make_plan(self.user, 'Sciolta', is_active=True)
        r = self._reorder(self.folder.pk, [plan.pk])
        self.assertEqual(r.status_code, 200)
        plan.refresh_from_db()
        self.assertEqual(plan.folder, self.folder)

    def test_reorders_plans_already_inside(self):
        p1 = make_plan(self.user, 'Uno', is_active=True, folder=self.folder, order=0)
        p2 = make_plan(self.user, 'Due', is_active=True, folder=self.folder, order=1)
        self._reorder(self.folder.pk, [p2.pk, p1.pk])
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p2.order, 0)
        self.assertEqual(p1.order, 1)

    def test_invalid_folder_404(self):
        r = self._reorder(9999, [])
        self.assertEqual(r.status_code, 404)

    def test_other_users_folder_rejected(self):
        other = make_user('folderother')
        self.client.login(username='folderother', password='testpass')
        r = self._reorder(self.folder.pk, [])
        self.assertEqual(r.status_code, 404)

    def test_other_users_plan_rejected(self):
        other = make_user('folderother2')
        other_plan = make_plan(other, 'Non mia', is_active=True)
        r = self._reorder(self.folder.pk, [other_plan.pk])
        self.assertEqual(r.status_code, 400)


class PlanFolderCrudTest(TestCase):
    def setUp(self):
        self.user = make_user('foldercrud')
        self.client.login(username='foldercrud', password='testpass')

    def test_create_folder(self):
        r = self.client.post(reverse('plan_folder_create'), {'name': 'Forza'})
        self.assertRedirects(r, reverse('plan_list'), fetch_redirect_response=False)
        self.assertEqual(PlanFolder.objects.filter(user=self.user, name='Forza').count(), 1)

    def test_create_empty_name_does_not_create_folder(self):
        self.client.post(reverse('plan_folder_create'), {'name': ''})
        self.assertEqual(PlanFolder.objects.count(), 0)

    def test_rename_folder(self):
        folder = make_folder(self.user, 'Vecchio nome')
        self.client.post(reverse('plan_folder_rename', kwargs={'pk': folder.pk}), {'name': 'Nuovo nome'})
        folder.refresh_from_db()
        self.assertEqual(folder.name, 'Nuovo nome')

    def test_rename_other_users_folder_404(self):
        other = make_user('cruother')
        folder = make_folder(other, 'Non mia')
        r = self.client.post(reverse('plan_folder_rename', kwargs={'pk': folder.pk}), {'name': 'Hacked'})
        self.assertEqual(r.status_code, 404)

    def test_delete_folder_does_not_delete_plans(self):
        folder = make_folder(self.user, 'Da eliminare')
        plan = make_plan(self.user, 'Sopravvive', is_active=True, folder=folder)
        self.client.post(reverse('plan_folder_delete', kwargs={'pk': folder.pk}))
        self.assertFalse(PlanFolder.objects.filter(pk=folder.pk).exists())
        plan.refresh_from_db()
        self.assertIsNone(plan.folder)

    def test_delete_other_users_folder_404(self):
        other = make_user('cruother2')
        folder = make_folder(other, 'Non mia')
        r = self.client.post(reverse('plan_folder_delete', kwargs={'pk': folder.pk}))
        self.assertEqual(r.status_code, 404)


# ─── Export / Import ──────────────────────────────────────────────────────────

class PlanExportTest(TestCase):
    def setUp(self):
        self.user = make_user('exporter')
        self.client.login(username='exporter', password='testpass')
        self.plan = make_plan(self.user, 'Push Day')
        self.ex = make_exercise('Panca', MuscleGroup.CHEST)
        PlannedExercise.objects.create(
            plan=self.plan, exercise=self.ex,
            target_sets=4, target_reps=8, order=0
        )

    def _rows(self):
        import csv as csv_module
        import io
        r = self.client.get(reverse('plan_export', kwargs={'pk': self.plan.pk}))
        content = r.content.decode('utf-8-sig')
        return list(csv_module.reader(io.StringIO(content)))

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

    def test_export_header_includes_bodyweight_column(self):
        rows = self._rows()
        self.assertIn('corpo_libero', rows[1])

    def test_export_weighted_exercise_marked_no(self):
        rows = self._rows()
        exercise_row = rows[2]
        self.assertEqual(exercise_row[0], 'Panca')
        self.assertEqual(exercise_row[-1], 'no')

    def test_export_bodyweight_exercise_marked_si(self):
        bw_ex = make_exercise('Trazioni Export', MuscleGroup.BACK, is_bodyweight=True)
        PlannedExercise.objects.create(
            plan=self.plan, exercise=bw_ex,
            target_sets=3, target_reps=10, order=1
        )
        rows = self._rows()
        bw_row = next(row for row in rows[2:] if row[0] == 'Trazioni Export')
        self.assertEqual(bw_row[-1], 'si')


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

    def test_import_with_bodyweight_column_creates_bodyweight_exercise(self):
        csv_file = self._make_csv(rows=[['Trazioni Import', 'back', '3', '10', '0', '', 'si']])
        csv_file.name = 'test.csv'
        self.client.post(reverse('plan_import'), {'csv_file': csv_file})
        exercise = Exercise.objects.get(name='Trazioni Import')
        self.assertTrue(exercise.is_bodyweight)

    def test_import_bodyweight_no_creates_weighted_exercise(self):
        csv_file = self._make_csv(rows=[['Panca Import', 'chest', '4', '8', '0', '', 'no']])
        csv_file.name = 'test.csv'
        self.client.post(reverse('plan_import'), {'csv_file': csv_file})
        exercise = Exercise.objects.get(name='Panca Import')
        self.assertFalse(exercise.is_bodyweight)

    def test_import_without_bodyweight_column_defaults_to_weighted(self):
        """Retrocompatibilità con i CSV esportati prima di questa funzionalità."""
        csv_file = self._make_csv(rows=[['Squat Legacy', 'legs', '4', '6', '0', '']])
        csv_file.name = 'test.csv'
        self.client.post(reverse('plan_import'), {'csv_file': csv_file})
        exercise = Exercise.objects.get(name='Squat Legacy')
        self.assertFalse(exercise.is_bodyweight)

    def test_import_does_not_overwrite_existing_exercise_bodyweight_flag(self):
        """
        Il flag corpo_libero, come muscle_group, si applica solo agli
        esercizi creati automaticamente — non sovrascrive quelli esistenti.
        """
        make_exercise('Trazioni Esistente', MuscleGroup.BACK, is_bodyweight=True)
        csv_file = self._make_csv(rows=[['Trazioni Esistente', 'back', '3', '10', '0', '', 'no']])
        csv_file.name = 'test.csv'
        self.client.post(reverse('plan_import'), {'csv_file': csv_file})
        exercise = Exercise.objects.get(name='Trazioni Esistente')
        self.assertTrue(exercise.is_bodyweight)


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


# ─── Exercise Edit ────────────────────────────────────────────────────────────

class ExerciseEditTest(TestCase):
    def setUp(self):
        self.user = make_user('ex_editor')
        self.client.login(username='ex_editor', password='testpass')
        self.exercise = make_exercise('Squat Originale', MuscleGroup.LEGS)

    def _post(self, **kwargs):
        data = {'name': 'Squat Originale', 'muscle_group': MuscleGroup.LEGS, 'description': ''}
        data.update(kwargs)
        return self.client.post(reverse('exercise_edit', kwargs={'pk': self.exercise.pk}), data)

    def test_updates_name(self):
        self._post(name='Squat Bulgaro')
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.name, 'Squat Bulgaro')

    def test_updates_muscle_group(self):
        self._post(muscle_group=MuscleGroup.GLUTES)
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.muscle_group, MuscleGroup.GLUTES)

    def test_edit_predefined_exercise(self):
        predefined = make_exercise('Predefined Edit', MuscleGroup.CHEST)
        self.client.post(reverse('exercise_edit', kwargs={'pk': predefined.pk}), {
            'name': 'Predefined Edit Renamed', 'muscle_group': MuscleGroup.CHEST, 'description': '',
        })
        predefined.refresh_from_db()
        self.assertEqual(predefined.name, 'Predefined Edit Renamed')

    def test_redirects_to_exercise_list_on_success(self):
        r = self._post(name='Squat Redirect')
        self.assertRedirects(r, reverse('exercise_list'), fetch_redirect_response=False)

    def test_rejects_duplicate_name(self):
        make_exercise('Panca Esistente', MuscleGroup.CHEST)
        self._post(name='Panca Esistente')
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.name, 'Squat Originale')

    def test_get_shows_form_with_existing_data(self):
        r = self.client.get(reverse('exercise_edit', kwargs={'pk': self.exercise.pk}))
        self.assertContains(r, 'Squat Originale')

    def test_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse('exercise_edit', kwargs={'pk': self.exercise.pk}))
        self.assertIn(r.status_code, [301, 302])


# ─── Exercise Delete ──────────────────────────────────────────────────────────

class ExerciseDeleteTest(TestCase):
    def setUp(self):
        self.user = make_user('ex_deleter')
        self.client.login(username='ex_deleter', password='testpass')
        self.exercise = make_exercise('Squat Delete', MuscleGroup.LEGS)

    def test_delete_removes_exercise(self):
        self.client.post(reverse('exercise_delete', kwargs={'pk': self.exercise.pk}))
        self.assertFalse(Exercise.objects.filter(pk=self.exercise.pk).exists())

    def test_delete_predefined_exercise(self):
        predefined = make_exercise('Predefined', MuscleGroup.CHEST)
        self.client.post(reverse('exercise_delete', kwargs={'pk': predefined.pk}))
        self.assertFalse(Exercise.objects.filter(pk=predefined.pk).exists())

    def test_delete_also_removes_logs(self):
        make_log(self.user, self.exercise)
        make_log(self.user, self.exercise, weight=90)
        self.client.post(reverse('exercise_delete', kwargs={'pk': self.exercise.pk}))
        self.assertEqual(ExerciseLog.objects.filter(exercise=self.exercise).count(), 0)

    def test_redirects_to_exercise_list(self):
        r = self.client.post(reverse('exercise_delete', kwargs={'pk': self.exercise.pk}))
        self.assertRedirects(r, reverse('exercise_list'), fetch_redirect_response=False)

    def test_get_does_not_delete(self):
        self.client.get(reverse('exercise_delete', kwargs={'pk': self.exercise.pk}))
        self.assertTrue(Exercise.objects.filter(pk=self.exercise.pk).exists())


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

# ─── Sessioni di allenamento ──────────────────────────────────────────────────

class SessionCreateTest(TestCase):
    def setUp(self):
        self.user = make_user('sessioncreator')
        self.client.login(username='sessioncreator', password='testpass')
        self.plan = make_plan(self.user, 'Push Pull Legs')

    def test_creates_session_for_today(self):
        self.client.post(reverse('session_create'), {'plan_id': self.plan.pk})
        session = WorkoutSession.objects.get(user=self.user)
        self.assertEqual(session.date, timezone.localdate())
        self.assertEqual(session.plan_name, 'Push Pull Legs')
        self.assertEqual(session.plan, self.plan)

    def test_duplicate_same_day_is_idempotent(self):
        """Riconfermare la stessa scheda non deve creare doppioni né errori."""
        self.client.post(reverse('session_create'), {'plan_id': self.plan.pk})
        r = self.client.post(reverse('session_create'), {'plan_id': self.plan.pk})
        self.assertEqual(WorkoutSession.objects.filter(user=self.user).count(), 1)
        self.assertEqual(r.status_code, 302)

    def test_two_plans_same_day_creates_two_sessions(self):
        other_plan = make_plan(self.user, 'Full Body', order=1)
        self.client.post(reverse('session_create'), {'plan_id': self.plan.pk})
        self.client.post(reverse('session_create'), {'plan_id': other_plan.pk})
        self.assertEqual(WorkoutSession.objects.filter(user=self.user).count(), 2)

    def test_other_users_plan_rejected(self):
        other = make_user('altrosessioncreator')
        other_plan = make_plan(other, 'Non mia')
        r = self.client.post(reverse('session_create'), {'plan_id': other_plan.pk})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(WorkoutSession.objects.count(), 0)

    def test_get_does_not_create(self):
        self.client.get(reverse('session_create'))
        self.assertEqual(WorkoutSession.objects.count(), 0)

    def test_explicit_past_date_accepted(self):
        past = timezone.localdate() - timedelta(days=3)
        self.client.post(reverse('session_create'), {
            'plan_id': self.plan.pk, 'date': past.isoformat(),
        })
        self.assertTrue(WorkoutSession.objects.filter(date=past).exists())

    def test_future_date_rejected(self):
        future = timezone.localdate() + timedelta(days=1)
        self.client.post(reverse('session_create'), {
            'plan_id': self.plan.pk, 'date': future.isoformat(),
        })
        self.assertEqual(WorkoutSession.objects.count(), 0)

    def test_invalid_date_rejected(self):
        self.client.post(reverse('session_create'), {
            'plan_id': self.plan.pk, 'date': 'non-una-data',
        })
        self.assertEqual(WorkoutSession.objects.count(), 0)


class SessionDeleteTest(TestCase):
    def setUp(self):
        self.user = make_user('sessiondeleter')
        self.client.login(username='sessiondeleter', password='testpass')
        self.plan = make_plan(self.user)
        self.session = WorkoutSession.objects.create(
            user=self.user, date=timezone.localdate(), plan=self.plan
        )

    def test_delete_removes_session(self):
        self.client.post(reverse('session_delete', kwargs={'pk': self.session.pk}))
        self.assertFalse(WorkoutSession.objects.filter(pk=self.session.pk).exists())

    def test_get_does_not_delete(self):
        self.client.get(reverse('session_delete', kwargs={'pk': self.session.pk}))
        self.assertTrue(WorkoutSession.objects.filter(pk=self.session.pk).exists())

    def test_other_users_session_404(self):
        other = make_user('altrodeleter')
        self.client.login(username='altrodeleter', password='testpass')
        r = self.client.post(reverse('session_delete', kwargs={'pk': self.session.pk}))
        self.assertEqual(r.status_code, 404)
        self.assertTrue(WorkoutSession.objects.filter(pk=self.session.pk).exists())


class PlanDetailSessionStateTest(TestCase):
    def setUp(self):
        self.user = make_user('detailsession')
        self.client.login(username='detailsession', password='testpass')
        self.plan = make_plan(self.user, 'Push Pull Legs')

    def test_flag_false_when_not_logged(self):
        r = self.client.get(reverse('plan_detail', kwargs={'pk': self.plan.pk}))
        self.assertFalse(r.context['session_logged_today'])

    def test_flag_true_after_logging(self):
        WorkoutSession.objects.create(
            user=self.user, date=timezone.localdate(), plan=self.plan
        )
        r = self.client.get(reverse('plan_detail', kwargs={'pk': self.plan.pk}))
        self.assertTrue(r.context['session_logged_today'])

    def test_yesterday_session_does_not_set_flag(self):
        WorkoutSession.objects.create(
            user=self.user, date=timezone.localdate() - timedelta(days=1), plan=self.plan
        )
        r = self.client.get(reverse('plan_detail', kwargs={'pk': self.plan.pk}))
        self.assertFalse(r.context['session_logged_today'])

    def test_other_plan_session_does_not_set_flag(self):
        other_plan = make_plan(self.user, 'Full Body', order=1)
        WorkoutSession.objects.create(
            user=self.user, date=timezone.localdate(), plan=other_plan
        )
        r = self.client.get(reverse('plan_detail', kwargs={'pk': self.plan.pk}))
        self.assertFalse(r.context['session_logged_today'])


# ─── Calendario ───────────────────────────────────────────────────────────────

class WorkoutCalendarTest(TestCase):
    def setUp(self):
        self.user = make_user('calendaruser')
        self.client.login(username='calendaruser', password='testpass')

    def test_calendar_renders(self):
        r = self.client.get(reverse('workout_calendar'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['weekday_names']), 7)

    def test_defaults_to_current_month(self):
        today = timezone.localdate()
        r = self.client.get(reverse('workout_calendar'))
        self.assertEqual(r.context['year'], today.year)
        self.assertEqual(r.context['month'], today.month)
        self.assertTrue(r.context['is_current_month'])

    def test_explicit_month(self):
        r = self.client.get(reverse('workout_calendar'), {'year': 2026, 'month': 3})
        self.assertEqual(r.context['year'], 2026)
        self.assertEqual(r.context['month'], 3)
        self.assertEqual(r.context['month_name'], 'Marzo')

    def test_invalid_month_falls_back_to_today(self):
        today = timezone.localdate()
        r = self.client.get(reverse('workout_calendar'), {'year': 2026, 'month': 99})
        self.assertEqual(r.context['month'], today.month)

    def test_non_numeric_params_fall_back_to_today(self):
        today = timezone.localdate()
        r = self.client.get(reverse('workout_calendar'), {'year': 'abc', 'month': 'xyz'})
        self.assertEqual(r.context['year'], today.year)

    def test_sessions_appear_in_grid(self):
        WorkoutSession.objects.create(
            user=self.user, date=date(2026, 3, 10), plan_name='Push'
        )
        r = self.client.get(reverse('workout_calendar'), {'year': 2026, 'month': 3})
        cells = [c for week in r.context['weeks'] for c in week if c and c['sessions']]
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0]['day'], 10)

    def test_other_users_sessions_not_shown(self):
        other = make_user('altrocalendar')
        WorkoutSession.objects.create(
            user=other, date=date(2026, 3, 10), plan_name='Non mia'
        )
        r = self.client.get(reverse('workout_calendar'), {'year': 2026, 'month': 3})
        cells = [c for week in r.context['weeks'] for c in week if c and c['sessions']]
        self.assertEqual(cells, [])

    def test_days_trained_counts_distinct_days(self):
        WorkoutSession.objects.create(user=self.user, date=date(2026, 3, 10), plan_name='A')
        WorkoutSession.objects.create(user=self.user, date=date(2026, 3, 10), plan_name='B')
        WorkoutSession.objects.create(user=self.user, date=date(2026, 3, 12), plan_name='A')
        r = self.client.get(reverse('workout_calendar'), {'year': 2026, 'month': 3})
        self.assertEqual(r.context['days_trained_this_month'], 2)
        self.assertEqual(r.context['total_days_trained'], 2)

    def test_prev_next_month_wraps_year(self):
        r = self.client.get(reverse('workout_calendar'), {'year': 2026, 'month': 1})
        self.assertEqual((r.context['prev_year'], r.context['prev_month']), (2025, 12))
        r = self.client.get(reverse('workout_calendar'), {'year': 2026, 'month': 12})
        self.assertEqual((r.context['next_year'], r.context['next_month']), (2027, 1))

    def test_streak_counts_consecutive_days(self):
        today = timezone.localdate()
        for offset in (0, 1, 2):
            WorkoutSession.objects.create(
                user=self.user, date=today - timedelta(days=offset), plan_name='A'
            )
        r = self.client.get(reverse('workout_calendar'))
        self.assertEqual(r.context['streak'], 3)

    def test_streak_survives_if_last_workout_was_yesterday(self):
        """Una giornata ancora in corso non deve azzerare la serie."""
        today = timezone.localdate()
        WorkoutSession.objects.create(
            user=self.user, date=today - timedelta(days=1), plan_name='A'
        )
        r = self.client.get(reverse('workout_calendar'))
        self.assertEqual(r.context['streak'], 1)

    def test_streak_zero_if_gap(self):
        today = timezone.localdate()
        WorkoutSession.objects.create(
            user=self.user, date=today - timedelta(days=5), plan_name='A'
        )
        r = self.client.get(reverse('workout_calendar'))
        self.assertEqual(r.context['streak'], 0)


class SessionDayDetailTest(TestCase):
    def setUp(self):
        self.user = make_user('daydetail')
        self.client.login(username='daydetail', password='testpass')
        self.plan = make_plan(self.user, 'Push Pull Legs')

    def test_returns_sessions_for_day(self):
        WorkoutSession.objects.create(
            user=self.user, date=date(2026, 3, 10), plan=self.plan
        )
        r = self.client.get(reverse('session_day_detail', args=[2026, 3, 10]))
        data = r.json()
        self.assertEqual(len(data['sessions']), 1)
        self.assertEqual(data['sessions'][0]['plan_name'], 'Push Pull Legs')
        self.assertEqual(data['date_label'], '10 Marzo 2026')

    def test_empty_day_returns_empty_list(self):
        r = self.client.get(reverse('session_day_detail', args=[2026, 3, 10]))
        self.assertEqual(r.json()['sessions'], [])

    def test_invalid_date_returns_400(self):
        r = self.client.get(reverse('session_day_detail', args=[2026, 2, 31]))
        self.assertEqual(r.status_code, 400)

    def test_session_without_plan_has_no_plan_url(self):
        WorkoutSession.objects.create(
            user=self.user, date=date(2026, 3, 10), plan_name='Scheda sparita'
        )
        r = self.client.get(reverse('session_day_detail', args=[2026, 3, 10]))
        self.assertIsNone(r.json()['sessions'][0]['plan_url'])

    def test_other_users_sessions_excluded(self):
        other = make_user('altrodaydetail')
        WorkoutSession.objects.create(
            user=other, date=date(2026, 3, 10), plan_name='Non mia'
        )
        r = self.client.get(reverse('session_day_detail', args=[2026, 3, 10]))
        self.assertEqual(r.json()['sessions'], [])


# ─── Import CSV allenamenti ───────────────────────────────────────────────────

class SessionImportTest(TestCase):
    def setUp(self):
        self.user = make_user('sessionimporter')
        self.client.login(username='sessionimporter', password='testpass')

    def _csv(self, content):
        import io
        f = io.BytesIO(content.encode('utf-8-sig'))
        f.name = 'sessions.csv'
        return f

    def test_import_creates_sessions(self):
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('data,scheda\n2026-01-15,Push\n2026-01-17,Pull\n')
        })
        self.assertEqual(WorkoutSession.objects.filter(user=self.user).count(), 2)

    def test_header_is_optional(self):
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('2026-01-15,Push\n')
        })
        self.assertEqual(WorkoutSession.objects.count(), 1)

    def test_italian_date_format_accepted(self):
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('15/01/2026,Push\n')
        })
        session = WorkoutSession.objects.get()
        self.assertEqual(session.date, date(2026, 1, 15))

    def test_links_existing_plan_by_name(self):
        plan = make_plan(self.user, 'Push')
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('2026-01-15,Push\n')
        })
        self.assertEqual(WorkoutSession.objects.get().plan, plan)

    def test_unknown_plan_stored_as_name_only(self):
        """Le schede sconosciute non vengono create come WorkoutPlan."""
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('2026-01-15,Scheda Mai Esistita\n')
        })
        session = WorkoutSession.objects.get()
        self.assertIsNone(session.plan)
        self.assertEqual(session.plan_name, 'Scheda Mai Esistita')
        self.assertEqual(WorkoutPlan.objects.count(), 0)

    def test_duplicates_in_file_ignored(self):
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('2026-01-15,Push\n2026-01-15,Push\n')
        })
        self.assertEqual(WorkoutSession.objects.count(), 1)

    def test_existing_session_not_duplicated(self):
        WorkoutSession.objects.create(
            user=self.user, date=date(2026, 1, 15), plan_name='Push'
        )
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('2026-01-15,Push\n2026-01-16,Pull\n')
        })
        self.assertEqual(WorkoutSession.objects.count(), 2)

    def test_future_dates_skipped(self):
        future = (timezone.localdate() + timedelta(days=5)).isoformat()
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv(f'2026-01-15,Push\n{future},Futuro\n')
        })
        self.assertEqual(WorkoutSession.objects.count(), 1)

    def test_invalid_date_row_skipped_but_others_imported(self):
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('data,scheda\nnon-una-data,Push\n2026-01-16,Pull\n')
        })
        self.assertEqual(WorkoutSession.objects.count(), 1)
        self.assertEqual(WorkoutSession.objects.get().plan_name, 'Pull')

    def test_row_without_plan_name_skipped(self):
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('2026-01-15,\n2026-01-16,Pull\n')
        })
        self.assertEqual(WorkoutSession.objects.count(), 1)

    def test_all_rows_invalid_reports_error(self):
        r = self.client.post(reverse('session_import'), {
            'csv_file': self._csv('non-una-data,Push\n')
        })
        self.assertEqual(WorkoutSession.objects.count(), 0)
        self.assertContains(r, 'Nessuna riga valida')

    def test_malformed_first_row_is_not_swallowed_as_header(self):
        """
        Regressione: una prima riga con data scritta male non deve essere
        scambiata per intestazione e scartata in silenzio; le altre righe
        valide vanno comunque importate.
        """
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('15-gennaio-2026,Push\n2026-01-16,Pull\n')
        })
        self.assertEqual(WorkoutSession.objects.count(), 1)
        self.assertTrue(WorkoutSession.objects.filter(plan_name='Pull').exists())
        self.assertFalse(WorkoutSession.objects.filter(plan_name='Push').exists())

    def test_header_variants_recognised(self):
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('Date,Plan\n2026-01-15,Push\n')
        })
        self.assertEqual(WorkoutSession.objects.count(), 1)


    def test_wrong_extension_rejected(self):
        import io
        f = io.BytesIO(b'2026-01-15,Push\n')
        f.name = 'sessions.txt'
        r = self.client.post(reverse('session_import'), {'csv_file': f})
        self.assertContains(r, 'formato CSV')
        self.assertEqual(WorkoutSession.objects.count(), 0)

    def test_missing_file_rejected(self):
        r = self.client.post(reverse('session_import'), {})
        self.assertContains(r, 'Nessun file')

    def test_empty_file_rejected(self):
        r = self.client.post(reverse('session_import'), {'csv_file': self._csv('')})
        self.assertContains(r, 'vuoto')

    def test_get_shows_form(self):
        r = self.client.get(reverse('session_import'))
        self.assertEqual(r.status_code, 200)

    def test_import_belongs_to_requesting_user(self):
        other = make_user('altroimporter')
        self.client.post(reverse('session_import'), {
            'csv_file': self._csv('2026-01-15,Push\n')
        })
        self.assertEqual(WorkoutSession.objects.filter(user=self.user).count(), 1)
        self.assertEqual(WorkoutSession.objects.filter(user=other).count(), 0)


class SessionImportDelimiterTest(TestCase):
    """Il separatore va riconosciuto da solo: virgola, ; , tab o pipe."""

    def setUp(self):
        self.user = make_user('delimuser')
        self.client.login(username='delimuser', password='testpass')

    def _post(self, content):
        f = io.BytesIO(content.encode('utf-8-sig'))
        f.name = 'sessions.csv'
        return self.client.post(reverse('session_import'), {'csv_file': f})

    def test_comma(self):
        self._post('data,scheda\n2026-01-15,Push\n')
        self.assertEqual(WorkoutSession.objects.get().plan_name, 'Push')

    def test_semicolon(self):
        self._post('data;scheda\n2026-01-15;Push\n')
        self.assertEqual(WorkoutSession.objects.get().plan_name, 'Push')

    def test_tab(self):
        self._post('data\tscheda\n2026-01-15\tPush\n')
        self.assertEqual(WorkoutSession.objects.get().plan_name, 'Push')

    def test_pipe(self):
        self._post('data|scheda\n2026-01-15|Push\n')
        self.assertEqual(WorkoutSession.objects.get().plan_name, 'Push')

    def test_semicolon_wins_over_commas_inside_plan_name(self):
        """
        Il caso che il semplice conteggio di occorrenze sbaglierebbe: il nome
        scheda contiene piu virgole di quanti siano i punti e virgola.
        """
        self._post('2026-01-15;Push, Pull, Legs\n')
        session = WorkoutSession.objects.get()
        self.assertEqual(session.plan_name, 'Push, Pull, Legs')
        self.assertEqual(session.date, date(2026, 1, 15))

    def test_tab_wins_over_commas_inside_plan_name(self):
        self._post('2026-01-15\tPush, Pull, Legs\n')
        self.assertEqual(WorkoutSession.objects.get().plan_name, 'Push, Pull, Legs')

    def test_quoted_comma_file_still_works(self):
        """Le virgolette restano il modo canonico di proteggere le virgole."""
        self._post('2026-01-15,"Push, Pull, Legs"\n')
        self.assertEqual(WorkoutSession.objects.get().plan_name, 'Push, Pull, Legs')

    def test_multiple_rows_semicolon(self):
        self._post('data;scheda\n2026-01-15;Push\n2026-01-16;Pull\n2026-01-17;Legs\n')
        self.assertEqual(WorkoutSession.objects.count(), 3)

    def test_single_column_file_reports_error(self):
        r = self._post('2026-01-15\n2026-01-16\n')
        self.assertEqual(WorkoutSession.objects.count(), 0)
        self.assertContains(r, 'Nessuna riga valida')


class SessionTemplateDownloadTest(TestCase):
    def setUp(self):
        self.user = make_user('templateuser')
        self.client.login(username='templateuser', password='testpass')

    def test_download_returns_csv(self):
        r = self.client.get(reverse('session_template_download'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r['Content-Type'])
        self.assertIn('attachment', r['Content-Disposition'])
        self.assertIn('.csv', r['Content-Disposition'])

    def test_template_has_header(self):
        r = self.client.get(reverse('session_template_download'))
        self.assertIn('data', r.content.decode('utf-8-sig'))
        self.assertIn('scheda', r.content.decode('utf-8-sig'))

    def test_template_uses_users_plan_names(self):
        make_plan(self.user, 'La Mia Scheda')
        body = self.client.get(reverse('session_template_download')).content.decode('utf-8-sig')
        self.assertIn('La Mia Scheda', body)

    def test_template_without_plans_uses_examples(self):
        body = self.client.get(reverse('session_template_download')).content.decode('utf-8-sig')
        self.assertIn('Push Pull Legs', body)

    def test_template_does_not_leak_other_users_plans(self):
        other = make_user('altrotemplate')
        make_plan(other, 'Scheda Segreta')
        body = self.client.get(reverse('session_template_download')).content.decode('utf-8-sig')
        self.assertNotIn('Scheda Segreta', body)

    def test_template_dates_are_in_the_past(self):
        """Le righe di esempio non devono essere scartate se reimportate."""
        make_plan(self.user, 'Scheda A')
        body = self.client.get(reverse('session_template_download')).content.decode('utf-8-sig')
        rows = [r for r in body.strip().split('\n')[1:] if r.strip()]
        self.assertTrue(rows)
        for row in rows:
            row_date = date.fromisoformat(row.split(',')[0].strip())
            self.assertLess(row_date, timezone.localdate())

    def test_downloaded_template_can_be_reimported(self):
        """Il modello scaricato deve essere accettato dall'import senza modifiche."""
        make_plan(self.user, 'Scheda A')
        body = self.client.get(reverse('session_template_download')).content
        f = io.BytesIO(body)
        f.name = 'template.csv'
        self.client.post(reverse('session_import'), {'csv_file': f})
        self.assertEqual(WorkoutSession.objects.filter(user=self.user).count(), 1)
        self.assertEqual(WorkoutSession.objects.get().plan_name, 'Scheda A')

    def test_requires_login(self):
        self.client.logout()
        r = self.client.get(reverse('session_template_download'))
        self.assertEqual(r.status_code, 302)
