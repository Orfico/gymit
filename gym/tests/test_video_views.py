"""Gestione dei video tutorial: permessi, form, rendering e data migration."""

import logging
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from gym.forms import ExerciseVideoForm
from gym.models import Exercise, MuscleGroup

VALID_ID = 'dQw4w9WgXcQ'
VALID_URL = f'https://www.youtube.com/watch?v={VALID_ID}'


def make_exercise(name='Panca Piana', video_id=None):
    return Exercise.objects.create(
        name=name, muscle_group=MuscleGroup.CHEST, youtube_video_id=video_id
    )


def patch_video_exists(result=True):
    """Evita chiamate di rete vere nei test delle viste e del form."""
    return patch('gym.forms.youtube.video_exists', return_value=result)


class ExerciseVideoFormTest(TestCase):
    def test_valid_url_extracts_id(self):
        with patch_video_exists(True):
            form = ExerciseVideoForm(data={'url': VALID_URL})
            self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.video_id, VALID_ID)

    def test_short_url_accepted(self):
        with patch_video_exists(True):
            form = ExerciseVideoForm(data={'url': f'https://youtu.be/{VALID_ID}?si=x'})
            self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.video_id, VALID_ID)

    def test_non_youtube_url_rejected(self):
        form = ExerciseVideoForm(data={'url': 'https://vimeo.com/123456'})
        self.assertFalse(form.is_valid())
        self.assertIn('Link non valido', form.errors['url'][0])

    def test_missing_video_rejected(self):
        with patch_video_exists(False):
            form = ExerciseVideoForm(data={'url': VALID_URL})
            self.assertFalse(form.is_valid())
        self.assertIn('non trovato', form.errors['url'][0])

    def test_unverifiable_video_accepted_with_warning(self):
        """Se la rete non risponde non si blocca l'admin, ma resta un log."""
        with patch_video_exists(None):
            with self.assertLogs('gym.forms', level=logging.WARNING) as captured:
                form = ExerciseVideoForm(data={'url': VALID_URL})
                self.assertTrue(form.is_valid(), form.errors)
        self.assertIn(VALID_ID, captured.output[0])

    def test_empty_url_rejected(self):
        form = ExerciseVideoForm(data={'url': ''})
        self.assertFalse(form.is_valid())


class ExerciseVideoPermissionTest(TestCase):
    def setUp(self):
        self.exercise = make_exercise()
        self.admin = User.objects.create_user('adminuser', password='pass', is_staff=True)
        self.plain = User.objects.create_user('plainuser', password='pass')

    def test_anonymous_redirected_to_login(self):
        response = self.client.post(
            reverse('exercise_video_set', args=[self.exercise.pk]), {'url': VALID_URL}
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/users/login/', response['Location'])

    def test_regular_user_forbidden(self):
        self.client.login(username='plainuser', password='pass')
        with patch_video_exists(True):
            response = self.client.post(
                reverse('exercise_video_set', args=[self.exercise.pk]), {'url': VALID_URL}
            )
        self.assertEqual(response.status_code, 403)
        self.exercise.refresh_from_db()
        self.assertIsNone(self.exercise.youtube_video_id)

    def test_regular_user_cannot_remove(self):
        self.exercise.youtube_video_id = VALID_ID
        self.exercise.save()
        self.client.login(username='plainuser', password='pass')
        response = self.client.post(
            reverse('exercise_video_remove', args=[self.exercise.pk])
        )
        self.assertEqual(response.status_code, 403)
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.youtube_video_id, VALID_ID)

    def test_admin_can_set_video(self):
        self.client.login(username='adminuser', password='pass')
        with patch_video_exists(True):
            response = self.client.post(
                reverse('exercise_video_set', args=[self.exercise.pk]), {'url': VALID_URL}
            )
        self.assertEqual(response.status_code, 302)
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.youtube_video_id, VALID_ID)
        self.assertEqual(self.exercise.video_added_by, self.admin)
        self.assertIsNotNone(self.exercise.video_added_at)

    def test_admin_can_replace_video(self):
        self.exercise.youtube_video_id = 'aaaaaaaaaaa'
        self.exercise.save()
        self.client.login(username='adminuser', password='pass')
        with patch_video_exists(True):
            self.client.post(
                reverse('exercise_video_set', args=[self.exercise.pk]), {'url': VALID_URL}
            )
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.youtube_video_id, VALID_ID)

    def test_admin_can_remove_video(self):
        self.exercise.youtube_video_id = VALID_ID
        self.exercise.video_added_by = self.admin
        self.exercise.save()
        self.client.login(username='adminuser', password='pass')
        self.client.post(reverse('exercise_video_remove', args=[self.exercise.pk]))
        self.exercise.refresh_from_db()
        self.assertIsNone(self.exercise.youtube_video_id)
        self.assertIsNone(self.exercise.video_added_by)
        self.assertIsNone(self.exercise.video_added_at)

    def test_invalid_url_reports_error_and_changes_nothing(self):
        self.client.login(username='adminuser', password='pass')
        response = self.client.post(
            reverse('exercise_video_set', args=[self.exercise.pk]),
            {'url': 'https://vimeo.com/123'},
            follow=True,
        )
        self.exercise.refresh_from_db()
        self.assertIsNone(self.exercise.youtube_video_id)
        self.assertContains(response, 'Link non valido')

    def test_get_on_set_is_a_noop_redirect(self):
        self.client.login(username='adminuser', password='pass')
        response = self.client.get(reverse('exercise_video_set', args=[self.exercise.pk]))
        self.assertEqual(response.status_code, 302)
        self.exercise.refresh_from_db()
        self.assertIsNone(self.exercise.youtube_video_id)

    def test_get_on_remove_is_a_noop_redirect(self):
        self.exercise.youtube_video_id = VALID_ID
        self.exercise.save()
        self.client.login(username='adminuser', password='pass')
        response = self.client.get(
            reverse('exercise_video_remove', args=[self.exercise.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.youtube_video_id, VALID_ID)

    def test_unknown_exercise_returns_404(self):
        self.client.login(username='adminuser', password='pass')
        response = self.client.post(reverse('exercise_video_set', args=[99999]),
                                    {'url': VALID_URL})
        self.assertEqual(response.status_code, 404)


class ExerciseVideoRenderingTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('adminview', password='pass', is_staff=True)
        self.plain = User.objects.create_user('plainview', password='pass')

    def _get(self, exercise):
        return self.client.get(reverse('exercise_progress', args=[exercise.pk]))

    def test_no_video_section_without_video(self):
        exercise = make_exercise('Senza Video')
        self.client.login(username='plainview', password='pass')
        response = self._get(exercise)
        self.assertNotContains(response, 'Vedi video')

    def test_video_section_visible_to_regular_user(self):
        exercise = make_exercise('Con Video', video_id=VALID_ID)
        self.client.login(username='plainview', password='pass')
        response = self._get(exercise)
        self.assertContains(response, 'Vedi video')

    def test_iframe_absent_from_initial_dom(self):
        """Il player deve nascere solo dopo il clic dell'utente."""
        exercise = make_exercise('Con Video', video_id=VALID_ID)
        self.client.login(username='plainview', password='pass')
        response = self._get(exercise)
        self.assertNotContains(response, '<iframe')

    def test_no_google_asset_is_preloaded(self):
        """
        Nessun attributo che scateni una richiesta a Google: gli indirizzi
        stanno in `data-`, che il browser non carica.
        """
        exercise = make_exercise('Con Video', video_id=VALID_ID)
        self.client.login(username='plainview', password='pass')
        html = self._get(exercise).content.decode()
        self.assertNotIn('src="https://img.youtube.com', html)
        self.assertNotIn('src="https://www.youtube-nocookie.com', html)
        self.assertIn('data-thumb-url="https://img.youtube.com', html)
        self.assertIn('data-embed-url="https://www.youtube-nocookie.com', html)

    def test_embed_url_uses_nocookie_domain(self):
        exercise = make_exercise('Con Video', video_id=VALID_ID)
        self.client.login(username='plainview', password='pass')
        self.assertContains(self._get(exercise), 'youtube-nocookie.com/embed/')

    def test_admin_form_hidden_from_regular_user(self):
        exercise = make_exercise('Con Video', video_id=VALID_ID)
        self.client.login(username='plainview', password='pass')
        response = self._get(exercise)
        self.assertNotContains(response, 'Video tutorial (admin)')
        self.assertFalse(response.context['can_manage_video'])

    def test_admin_sees_form(self):
        exercise = make_exercise('Senza Video')
        self.client.login(username='adminview', password='pass')
        response = self._get(exercise)
        self.assertContains(response, 'Video tutorial (admin)')
        self.assertContains(response, 'Aggiungi un video')
        self.assertTrue(response.context['can_manage_video'])

    def test_admin_sees_attribution_and_remove_button(self):
        exercise = make_exercise('Con Video', video_id=VALID_ID)
        exercise.video_added_by = self.admin
        exercise.save()
        self.client.login(username='adminview', password='pass')
        response = self._get(exercise)
        self.assertContains(response, 'Aggiunto da')
        self.assertContains(response, 'adminview')
        self.assertContains(response, 'Rimuovi')

    def test_username_is_escaped(self):
        exercise = make_exercise('Con Video', video_id=VALID_ID)
        nasty = User.objects.create_user('<script>x</script>', password='pass', is_staff=True)
        exercise.video_added_by = nasty
        exercise.save()
        self.client.login(username='adminview', password='pass')
        html = self._get(exercise).content.decode()
        self.assertNotIn('<script>x</script>', html)
        self.assertIn('&lt;script&gt;', html)


class PromoteAdminMigrationTest(TestCase):
    """
    La data migration viene richiamata direttamente: interessa il suo
    comportamento (idempotenza, utente assente), non il motore migrazioni.
    """

    MIGRATION = 'gym.migrations.0008_promote_video_admin'

    @classmethod
    def _module(cls):
        import importlib
        return importlib.import_module(cls.MIGRATION)

    @classmethod
    def _run(cls, username=None):
        """
        `username=None` esercita il default: si rimuove ADMIN_USERNAME
        dall'ambiente, così un valore impostato fuori dai test non falsa
        il risultato.
        """
        import os
        from django.apps import apps

        module = cls._module()
        with patch.dict('os.environ', {}, clear=False):
            if username is None:
                os.environ.pop('ADMIN_USERNAME', None)
            else:
                os.environ['ADMIN_USERNAME'] = username
            module.promote_admin(apps, None)
        return module

    def test_promotes_matching_user(self):
        user = User.objects.create_user('Luca', password='pass')
        self.assertFalse(user.is_staff)
        self._run()
        user.refresh_from_db()
        self.assertTrue(user.is_staff)

    def test_is_idempotent(self):
        user = User.objects.create_user('Luca', password='pass')
        self._run()
        self._run()
        self._run()
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertEqual(User.objects.filter(username='Luca').count(), 1)

    def test_match_is_case_insensitive(self):
        user = User.objects.create_user('luca', password='pass')
        self._run()
        user.refresh_from_db()
        self.assertTrue(user.is_staff)

    def test_missing_user_logs_warning_without_crashing(self):
        with self.assertLogs(
            'gym.migrations.0008_promote_video_admin', level=logging.WARNING
        ) as captured:
            self._run()
        self.assertIn('Nessun utente corrisponde', captured.output[0])

    def test_custom_username_from_env(self):
        user = User.objects.create_user('altroadmin', password='pass')
        self._run('altroadmin')
        user.refresh_from_db()
        self.assertTrue(user.is_staff)

    def test_matches_by_email_too(self):
        user = User.objects.create_user('qualcuno', password='pass', email='luca@example.test')
        self._run('luca@example.test')
        user.refresh_from_db()
        self.assertTrue(user.is_staff)

    def test_blank_env_var_does_nothing(self):
        user = User.objects.create_user('Luca', password='pass')
        with self.assertLogs(
            'gym.migrations.0008_promote_video_admin', level=logging.WARNING
        ):
            self._run('   ')
        user.refresh_from_db()
        self.assertFalse(user.is_staff)

    def test_does_not_touch_other_users(self):
        User.objects.create_user('Luca', password='pass')
        other = User.objects.create_user('altro', password='pass')
        self._run()
        other.refresh_from_db()
        self.assertFalse(other.is_staff)

    def test_reverse_is_a_noop(self):
        from django.apps import apps

        module = self._module()
        user = User.objects.create_user('Luca', password='pass', is_staff=True)
        module.noop_reverse(apps, None)
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
