"""Modifica di un esercizio già in scheda e preferenza sugli strumenti video."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from gym.models import (
    Exercise, MuscleGroup, PlannedExercise, UserPreferences, WorkoutPlan,
    shows_video_admin,
)


def make_planned(user, sets=3, reps=10, notes='', name='Panca Piana'):
    plan = WorkoutPlan.objects.create(user=user, name='Scheda Test')
    exercise = Exercise.objects.create(name=name, muscle_group=MuscleGroup.CHEST)
    return PlannedExercise.objects.create(
        plan=plan, exercise=exercise, target_sets=sets, target_reps=reps, notes=notes
    )


class PlannedExerciseEditTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('editor', password='pass')
        self.other = User.objects.create_user('altroeditor', password='pass')
        self.client.login(username='editor', password='pass')
        self.planned = make_planned(self.user)

    def _url(self, planned=None):
        return reverse('planned_exercise_edit', args=[(planned or self.planned).pk])

    def test_form_shows_current_values(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['form'].initial['target_sets'], 3)
        self.assertEqual(response.context['form'].initial['target_reps'], 10)

    def test_updates_sets_and_reps(self):
        response = self.client.post(self._url(), {
            'target_sets': 5, 'target_reps': 8, 'notes': '',
        })
        self.planned.refresh_from_db()
        self.assertEqual(self.planned.target_sets, 5)
        self.assertEqual(self.planned.target_reps, 8)
        self.assertRedirects(response, reverse('plan_detail', args=[self.planned.plan.pk]))

    def test_updates_notes(self):
        self.client.post(self._url(), {
            'target_sets': 3, 'target_reps': 10, 'notes': 'Pausa 90s',
        })
        self.planned.refresh_from_db()
        self.assertEqual(self.planned.notes, 'Pausa 90s')

    def test_exercise_cannot_be_changed(self):
        """L'esercizio non è nel form: un tentativo di cambiarlo va ignorato."""
        altro = Exercise.objects.create(name='Squat Edit', muscle_group=MuscleGroup.LEGS)
        original = self.planned.exercise_id
        self.client.post(self._url(), {
            'target_sets': 3, 'target_reps': 10, 'notes': '', 'exercise': altro.pk,
        })
        self.planned.refresh_from_db()
        self.assertEqual(self.planned.exercise_id, original)

    def test_order_is_preserved(self):
        self.planned.order = 7
        self.planned.save()
        self.client.post(self._url(), {
            'target_sets': 4, 'target_reps': 12, 'notes': '',
        })
        self.planned.refresh_from_db()
        self.assertEqual(self.planned.order, 7)

    def test_zero_sets_rejected(self):
        self.client.post(self._url(), {
            'target_sets': 0, 'target_reps': 10, 'notes': '',
        })
        self.planned.refresh_from_db()
        self.assertEqual(self.planned.target_sets, 3)

    def test_negative_reps_rejected(self):
        response = self.client.post(self._url(), {
            'target_sets': 3, 'target_reps': -5, 'notes': '',
        })
        self.assertEqual(response.status_code, 200)
        self.planned.refresh_from_db()
        self.assertEqual(self.planned.target_reps, 10)

    def test_other_users_entry_returns_404(self):
        foreign = make_planned(self.other, name='Stacco Altrui')
        response = self.client.get(self._url(foreign))
        self.assertEqual(response.status_code, 404)

    def test_other_user_cannot_post(self):
        foreign = make_planned(self.other, name='Rematore Altrui')
        response = self.client.post(self._url(foreign), {
            'target_sets': 9, 'target_reps': 9, 'notes': '',
        })
        self.assertEqual(response.status_code, 404)
        foreign.refresh_from_db()
        self.assertEqual(foreign.target_sets, 3)

    def test_anonymous_redirected_to_login(self):
        self.client.logout()
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response['Location'])

    def test_edit_link_present_in_plan_detail(self):
        response = self.client.get(reverse('plan_detail', args=[self.planned.plan.pk]))
        self.assertContains(response, self._url())


class VideoAdminPreferenceTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('prefadmin', password='pass', is_staff=True)
        self.plain = User.objects.create_user('prefplain', password='pass')
        self.exercise = Exercise.objects.create(
            name='Panca Pref', muscle_group=MuscleGroup.CHEST,
            youtube_video_id='dQw4w9WgXcQ',
        )

    # ── Helper del modello ───────────────────────────────────────────
    def test_defaults_to_true_for_admin(self):
        self.assertTrue(shows_video_admin(self.admin))

    def test_false_for_regular_user(self):
        self.assertFalse(shows_video_admin(self.plain))

    def test_no_row_created_just_by_reading(self):
        shows_video_admin(self.admin)
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_respects_stored_preference(self):
        UserPreferences.objects.create(user=self.admin, show_video_admin=False)
        self.assertFalse(shows_video_admin(self.admin))

    # ── Interruttore ─────────────────────────────────────────────────
    def test_admin_can_switch_off(self):
        self.client.login(username='prefadmin', password='pass')
        self.client.post(reverse('toggle_video_admin'), {'next': '/'})
        self.assertFalse(UserPreferences.objects.get(user=self.admin).show_video_admin)

    def test_admin_can_switch_back_on(self):
        UserPreferences.objects.create(user=self.admin, show_video_admin=False)
        self.client.login(username='prefadmin', password='pass')
        self.client.post(reverse('toggle_video_admin'),
                         {'show_video_admin': 'on', 'next': '/'})
        self.assertTrue(UserPreferences.objects.get(user=self.admin).show_video_admin)

    def test_regular_user_forbidden(self):
        self.client.login(username='prefplain', password='pass')
        response = self.client.post(reverse('toggle_video_admin'), {'next': '/'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(UserPreferences.objects.count(), 0)

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(reverse('toggle_video_admin'), {'next': '/'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response['Location'])

    def test_external_next_is_ignored(self):
        """`next` arriva dal client: un dominio esterno non deve essere seguito."""
        self.client.login(username='prefadmin', password='pass')
        response = self.client.post(reverse('toggle_video_admin'),
                                    {'next': 'https://esempio.invalido/phishing'})
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)

    def test_internal_next_is_followed(self):
        self.client.login(username='prefadmin', password='pass')
        target = reverse('exercise_progress', args=[self.exercise.pk])
        response = self.client.post(reverse('toggle_video_admin'), {'next': target})
        self.assertRedirects(response, target, fetch_redirect_response=False)

    # ── Effetto sulla pagina ─────────────────────────────────────────
    def _progress(self):
        return self.client.get(reverse('exercise_progress', args=[self.exercise.pk]))

    def test_tools_visible_by_default(self):
        self.client.login(username='prefadmin', password='pass')
        response = self._progress()
        self.assertTrue(response.context['can_manage_video'])
        self.assertContains(response, 'Video tutorial (admin)')

    def test_tools_hidden_when_switched_off(self):
        UserPreferences.objects.create(user=self.admin, show_video_admin=False)
        self.client.login(username='prefadmin', password='pass')
        response = self._progress()
        self.assertFalse(response.context['can_manage_video'])
        self.assertNotContains(response, 'Video tutorial (admin)')

    def test_video_still_visible_when_tools_hidden(self):
        """Nascondere gli strumenti non nasconde il video agli occhi dell'admin."""
        UserPreferences.objects.create(user=self.admin, show_video_admin=False)
        self.client.login(username='prefadmin', password='pass')
        self.assertContains(self._progress(), 'Vedi video')

    def test_hiding_tools_does_not_remove_permission(self):
        """
        È una preferenza di visualizzazione, non un permesso: chi è staff
        continua a poter scrivere anche con gli strumenti spenti.
        """
        UserPreferences.objects.create(user=self.admin, show_video_admin=False)
        self.client.login(username='prefadmin', password='pass')
        response = self.client.post(
            reverse('exercise_video_remove', args=[self.exercise.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.exercise.refresh_from_db()
        self.assertIsNone(self.exercise.youtube_video_id)

    # ── Interruttore nel menu ────────────────────────────────────────
    def test_switch_in_menu_for_admin(self):
        self.client.login(username='prefadmin', password='pass')
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, 'videoAdminPref')
        self.assertContains(response, 'Strumenti video')

    def test_switch_absent_for_regular_user(self):
        self.client.login(username='prefplain', password='pass')
        response = self.client.get(reverse('dashboard'))
        self.assertNotContains(response, 'videoAdminPref')

    def test_switch_reflects_stored_state(self):
        UserPreferences.objects.create(user=self.admin, show_video_admin=False)
        self.client.login(username='prefadmin', password='pass')
        html = self.client.get(reverse('dashboard')).content.decode()
        switch = html[html.index('id="videoAdminPref"'):][:200]
        self.assertNotIn('checked', switch)

    def test_context_processor_available_on_any_page(self):
        self.client.login(username='prefadmin', password='pass')
        response = self.client.get(reverse('plan_list'))
        self.assertTrue(response.context['shows_video_admin'])
