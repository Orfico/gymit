"""Strength standards: dati, profilo fisico, signal, vista e migration."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from gym import strength_standards as ss
from gym.models import Exercise, ExerciseLog, MuscleGroup, UserProfile
from gym.forms import UserProfileForm


def make_user(username='lifter'):
    return User.objects.create_user(username, password='pw')


def make_bench(standard_key='bench_press'):
    return Exercise.objects.create(
        name='Panca Piana', muscle_group=MuscleGroup.CHEST, standard_key=standard_key
    )


def fill_profile(user, **overrides):
    values = dict(
        body_weight=Decimal('80.0'), sex='M', training_level='intermediate',
        birth_date=None,
    )
    values.update(overrides)
    profile = user.userprofile
    for field, value in values.items():
        setattr(profile, field, value)
    profile.save()
    return profile


class AgeFactorTest(TestCase):
    def test_none_means_no_adjustment(self):
        self.assertEqual(ss.get_age_factor(None), 1.0)

    def test_up_to_40_is_unchanged(self):
        self.assertEqual(ss.get_age_factor(0), 1.0)
        self.assertEqual(ss.get_age_factor(25), 1.0)
        self.assertEqual(ss.get_age_factor(40), 1.0)

    def test_over_40_is_reduced(self):
        self.assertEqual(ss.get_age_factor(41), 0.97)
        self.assertEqual(ss.get_age_factor(52), 0.87)
        self.assertEqual(ss.get_age_factor(80), 0.68)

    def test_factor_never_increases_with_age(self):
        factors = [ss.get_age_factor(age) for age in range(0, 100)]
        self.assertEqual(factors, sorted(factors, reverse=True))


class ComputeBenchmarkTest(TestCase):
    def test_known_value_man_80kg_intermediate_bench(self):
        # Riga della tabella Strength Level: uomo, 80 kg, panca -> 98 kg
        self.assertEqual(ss.compute_benchmark('bench_press', 80, 'M', 'intermediate'), 98.0)

    def test_every_level_matches_table_row(self):
        expected = {'beginner': 56, 'novice': 75, 'intermediate': 98, 'advanced': 124, 'elite': 151}
        for level, kg in expected.items():
            self.assertEqual(ss.compute_benchmark('bench_press', 80, 'M', level), kg)

    def test_accepts_decimal_body_weight(self):
        self.assertEqual(
            ss.compute_benchmark('bench_press', Decimal('80.0'), 'M', 'intermediate'), 98.0
        )

    def test_woman_uses_her_own_table(self):
        self.assertEqual(ss.compute_benchmark('squat', 60, 'F', 'advanced'), 99.0)

    def test_interpolates_between_rows(self):
        # 80 kg -> 98, 85 kg -> 104: a meta strada 101
        self.assertEqual(ss.compute_benchmark('bench_press', 82.5, 'M', 'intermediate'), 101.0)
        # a 81 kg un quinto del percorso (+1,2)
        self.assertEqual(ss.compute_benchmark('bench_press', 81, 'M', 'intermediate'), 99.2)

    def test_ratio_is_not_constant_across_body_weights(self):
        """Il motivo delle tabelle: un moltiplicatore unico sbaglierebbe."""
        light = ss.compute_benchmark('bench_press', 60, 'M', 'beginner') / 60
        heavy = ss.compute_benchmark('bench_press', 100, 'M', 'beginner') / 100
        self.assertNotAlmostEqual(light, heavy, places=2)

    def test_outside_table_range_uses_nearest_row(self):
        self.assertEqual(ss.compute_benchmark('bench_press', 45, 'M', 'beginner'), 27.0)
        self.assertEqual(ss.compute_benchmark('bench_press', 200, 'M', 'elite'), 225.0)
        self.assertEqual(ss.compute_benchmark('bench_press', 30, 'F', 'beginner'), 10.0)
        self.assertEqual(ss.compute_benchmark('bench_press', 150, 'F', 'elite'), 128.0)

    def test_heavier_lifter_never_gets_lower_target(self):
        for key in ss.STANDARDS:
            for sex in ('M', 'F'):
                for level in ss.LEVELS:
                    values = [
                        ss.compute_benchmark(key, bw, sex, level)
                        for bw in range(30, 200, 3)
                    ]
                    self.assertEqual(values, sorted(values), f'{key}/{sex}/{level}')

    def test_age_adjustment_applied(self):
        # 98 kg x 0.87 (51-55 anni)
        self.assertEqual(
            ss.compute_benchmark('bench_press', 80, 'M', 'intermediate', age=53), 85.3
        )

    def test_under_40_same_as_no_age(self):
        self.assertEqual(
            ss.compute_benchmark('bench_press', 80, 'M', 'intermediate', age=30),
            ss.compute_benchmark('bench_press', 80, 'M', 'intermediate'),
        )

    def test_missing_data_returns_none(self):
        self.assertIsNone(ss.compute_benchmark('bench_press', None, 'M', 'intermediate'))
        self.assertIsNone(ss.compute_benchmark('bench_press', 0, 'M', 'intermediate'))
        self.assertIsNone(ss.compute_benchmark('bench_press', 80, None, 'intermediate'))
        self.assertIsNone(ss.compute_benchmark(None, 80, 'M', 'intermediate'))
        self.assertIsNone(ss.compute_benchmark('', 80, 'M', 'intermediate'))

    def test_unknown_values_return_none(self):
        self.assertIsNone(ss.compute_benchmark('curl', 80, 'M', 'intermediate'))
        self.assertIsNone(ss.compute_benchmark('bench_press', 80, 'X', 'intermediate'))
        self.assertIsNone(ss.compute_benchmark('bench_press', 80, 'M', 'godlike'))


class StandardTablesTest(TestCase):
    """Integrita dei dati: un errore di trascrizione si vedrebbe qui."""

    def test_every_standard_has_a_label_and_vice_versa(self):
        self.assertEqual(set(ss.STANDARDS), set(ss.STANDARD_LABELS))

    def test_tables_cover_both_sexes_with_regular_grid(self):
        grids = {'M': list(range(50, 145, 5)), 'F': list(range(40, 125, 5))}
        for key, by_sex in ss.STANDARDS.items():
            for sex, grid in grids.items():
                self.assertEqual([row[0] for row in by_sex[sex]], grid, f'{key}/{sex}')

    def test_rows_increase_across_levels(self):
        for key, by_sex in ss.STANDARDS.items():
            for sex, rows in by_sex.items():
                for row in rows:
                    self.assertEqual(len(row), 6, f'{key}/{sex}/{row}')
                    self.assertEqual(list(row[1:]), sorted(row[1:]), f'{key}/{sex}/{row}')

    def test_columns_increase_with_body_weight(self):
        for key, by_sex in ss.STANDARDS.items():
            for sex, rows in by_sex.items():
                for column in range(1, 6):
                    values = [row[column] for row in rows]
                    self.assertEqual(values, sorted(values), f'{key}/{sex}/{column}')

    def test_women_lift_less_than_men_at_same_weight(self):
        for key, by_sex in ss.STANDARDS.items():
            men = {row[0]: row for row in by_sex['M']}
            for woman in by_sex['F']:
                # Nella fonte, per l'hip thrust, le donne sotto i 60 kg hanno
                # valori pari o superiori agli uomini: e un dato reale, non
                # un errore di trascrizione (confermato da due letture).
                if key == 'hip_thrust' and woman[0] < 60:
                    continue
                if woman[0] in men:
                    self.assertLess(woman[3], men[woman[0]][3], f'{key}/{woman[0]}')


class AllBenchmarksTest(TestCase):
    def test_returns_kg_for_every_level(self):
        levels = ss.get_all_benchmarks('bench_press', 80, 'M')
        self.assertEqual(
            levels,
            {'beginner': 56.0, 'novice': 75.0, 'intermediate': 98.0,
             'advanced': 124.0, 'elite': 151.0},
        )

    def test_age_applied_to_every_level(self):
        levels = ss.get_all_benchmarks('bench_press', 80, 'M', age=53)
        self.assertEqual(levels['intermediate'], 85.3)

    def test_unknown_or_missing_returns_none(self):
        self.assertIsNone(ss.get_all_benchmarks('curl', 80, 'M'))
        self.assertIsNone(ss.get_all_benchmarks('bench_press', 80, 'X'))
        self.assertIsNone(ss.get_all_benchmarks('bench_press', None, 'M'))


class HighestLevelReachedTest(TestCase):
    def test_picks_highest_level_met(self):
        # 80 kg uomo, panca: novice 75, intermediate 98, advanced 124
        self.assertEqual(ss.highest_level_reached('bench_press', 80, 'M', 105), 'intermediate')
        self.assertEqual(ss.highest_level_reached('bench_press', 80, 'M', 98), 'intermediate')
        self.assertEqual(ss.highest_level_reached('bench_press', 80, 'M', 75), 'novice')

    def test_below_first_level_is_none(self):
        self.assertIsNone(ss.highest_level_reached('bench_press', 80, 'M', 30))

    def test_thresholds_follow_age(self):
        # A 53 anni il livello intermedio vale 85,3 kg, non 98.
        self.assertEqual(
            ss.highest_level_reached('bench_press', 80, 'M', 90, age=53), 'intermediate'
        )
        self.assertEqual(ss.highest_level_reached('bench_press', 80, 'M', 90), 'novice')


class UserProfileModelTest(TestCase):
    def profile_born(self, birth_date):
        return UserProfile(user=make_user(f'u{birth_date}'), birth_date=birth_date)

    def test_age_none_without_birth_date(self):
        self.assertIsNone(UserProfile(user=make_user()).age)

    def test_age_before_birthday_this_year(self):
        with patch('gym.models.date') as mock_date:
            mock_date.today.return_value = date(2026, 6, 15)
            self.assertEqual(self.profile_born(date(1990, 6, 16)).age, 35)

    def test_age_on_birthday(self):
        with patch('gym.models.date') as mock_date:
            mock_date.today.return_value = date(2026, 6, 15)
            self.assertEqual(self.profile_born(date(1990, 6, 15)).age, 36)

    def test_age_after_birthday(self):
        with patch('gym.models.date') as mock_date:
            mock_date.today.return_value = date(2026, 6, 15)
            self.assertEqual(self.profile_born(date(1990, 1, 1)).age, 36)

    def test_defaults(self):
        profile = make_user().userprofile
        self.assertIsNone(profile.body_weight)
        self.assertIsNone(profile.sex)
        self.assertEqual(profile.training_level, 'beginner')
        self.assertFalse(profile.has_benchmark_data)

    def test_has_benchmark_data_needs_weight_and_sex(self):
        profile = UserProfile(body_weight=Decimal('70'))
        self.assertFalse(profile.has_benchmark_data)
        profile.sex = 'F'
        self.assertTrue(profile.has_benchmark_data)


class UserProfileSignalTest(TestCase):
    def test_profile_created_with_user(self):
        user = make_user()
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_saving_user_again_does_not_duplicate(self):
        user = make_user()
        user.first_name = 'Mario'
        user.save()
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_profile_deleted_with_user(self):
        user = make_user()
        user.delete()
        self.assertEqual(UserProfile.objects.count(), 0)


class LegacyUserTest(TestCase):
    """Utenti registrati prima del profilo: nessuna riga, ma tutto funziona."""

    def setUp(self):
        self.user = make_user('legacy')
        UserProfile.objects.filter(user=self.user).delete()
        self.client.force_login(self.user)

    def test_backfill_creates_missing_profiles_only(self):
        import importlib
        from django.apps import apps
        migration = importlib.import_module('gym.migrations.0012_backfill_user_profiles')
        has_profile = make_user('modern')
        has_profile.userprofile.body_weight = Decimal('75')
        has_profile.userprofile.save()

        migration.backfill_profiles(apps, None)

        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
        self.assertEqual(UserProfile.objects.count(), 2)
        self.assertEqual(
            UserProfile.objects.get(user=has_profile).body_weight, Decimal('75')
        )
        migration.backfill_profiles(apps, None)  # idempotente
        self.assertEqual(UserProfile.objects.count(), 2)

    def test_profile_page_opens_without_row(self):
        response = self.client.get(reverse('physical_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_exercise_page_invites_to_fill_profile(self):
        exercise = make_bench()
        response = self.client.get(reverse('exercise_progress', args=[exercise.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('physical_profile'))

    def test_benchmark_appears_after_filling_profile(self):
        exercise = make_bench()
        self.client.post(reverse('physical_profile'), {
            'body_weight': '80', 'sex': 'M', 'training_level': 'intermediate',
        })
        response = self.client.get(reverse('exercise_progress', args=[exercise.pk]))
        self.assertEqual(response.context['benchmark_data']['benchmark_1rm'], 98.0)


class UserProfileFormTest(TestCase):
    def test_empty_form_is_valid(self):
        form = UserProfileForm(data={'training_level': 'beginner'})
        self.assertTrue(form.is_valid(), form.errors)

    def test_rejects_implausible_weight(self):
        for weight in ('5', '0', '999'):
            form = UserProfileForm(data={'training_level': 'beginner', 'body_weight': weight})
            self.assertFalse(form.is_valid(), weight)
            self.assertIn('body_weight', form.errors)

    def test_rejects_future_birth_date(self):
        form = UserProfileForm(data={'training_level': 'beginner', 'birth_date': '2999-01-01'})
        self.assertFalse(form.is_valid())
        self.assertIn('birth_date', form.errors)


class PhysicalProfileViewTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse('physical_profile')

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_get_renders_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Peso corporeo (kg)')

    def test_post_saves_profile(self):
        response = self.client.post(self.url, {
            'body_weight': '82.5', 'sex': 'M',
            'birth_date': '1990-03-02', 'training_level': 'advanced',
        })
        self.assertRedirects(response, self.url)
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.body_weight, Decimal('82.5'))
        self.assertEqual(profile.sex, 'M')
        self.assertEqual(profile.training_level, 'advanced')

    def test_user_without_profile_row_can_still_save(self):
        """Gli utenti precedenti al profilo non hanno la riga: la crea la vista."""
        UserProfile.objects.filter(user=self.user).delete()
        self.client.post(self.url, {'body_weight': '70', 'training_level': 'beginner'})
        self.assertEqual(UserProfile.objects.get(user=self.user).body_weight, Decimal('70'))

    def test_empty_post_does_not_block_user(self):
        response = self.client.post(self.url, {'training_level': 'beginner'})
        self.assertRedirects(response, self.url)

    def test_sex_labels_are_maschio_femmina(self):
        response = self.client.get(self.url)
        self.assertContains(response, '>Maschio<')
        self.assertContains(response, '>Femmina<')
        self.assertNotContains(response, '>Uomo<')
        self.assertNotContains(response, '>Donna<')

    def test_navbar_links_to_profile(self):
        response = self.client.get(reverse('dashboard'))
        self.assertContains(response, self.url)

    def test_each_user_edits_only_own_profile(self):
        other = make_user('other')
        self.client.post(self.url, {'body_weight': '90', 'training_level': 'elite'})
        self.assertIsNone(UserProfile.objects.get(user=other).body_weight)


class ExerciseProgressBenchmarkTest(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.exercise = make_bench()

    def get(self, exercise=None):
        exercise = exercise or self.exercise
        return self.client.get(reverse('exercise_progress', args=[exercise.pk]))

    def log(self, weight=100, reps=1):
        return ExerciseLog.objects.create(
            user=self.user, exercise=self.exercise, date=date.today(),
            sets=1, reps=reps, weight=weight,
        )

    def test_profile_incomplete_when_no_data(self):
        response = self.get()
        self.assertTrue(response.context['has_standard'])
        self.assertIs(response.context['profile_incomplete'], True)
        self.assertIsNone(response.context['benchmark_data'])
        self.assertContains(response, reverse('physical_profile'))

    def test_profile_incomplete_when_user_has_no_profile_row(self):
        UserProfile.objects.filter(user=self.user).delete()
        self.assertIs(self.get().context['profile_incomplete'], True)

    def test_profile_incomplete_with_weight_but_no_sex(self):
        fill_profile(self.user, sex=None)
        self.assertIs(self.get().context['profile_incomplete'], True)

    def test_no_card_for_exercise_without_standard(self):
        curl = Exercise.objects.create(name='Curl', muscle_group=MuscleGroup.BICEPS)
        response = self.get(curl)
        self.assertFalse(response.context['has_standard'])
        self.assertIs(response.context['profile_incomplete'], False)
        self.assertNotContains(response, 'bi-trophy')

    def test_unknown_standard_key_hides_card(self):
        fill_profile(self.user)
        response = self.get(self._with_key('inventato'))
        self.assertFalse(response.context['has_standard'])
        self.assertNotContains(response, 'bi-trophy')

    def _with_key(self, key):
        self.exercise.standard_key = key
        self.exercise.save()
        return self.exercise

    def test_benchmark_without_logs(self):
        fill_profile(self.user)
        data = self.get().context['benchmark_data']
        self.assertEqual(data['benchmark_1rm'], 98.0)
        self.assertIsNone(data['percentage'])
        self.assertIsNone(data['current_level'])
        self.assertIs(self.get().context['profile_incomplete'], False)

    def test_benchmark_with_logs(self):
        fill_profile(self.user)
        self.log(weight=80, reps=1)
        data = self.get().context['benchmark_data']
        self.assertEqual(data['benchmark_1rm'], 98.0)
        self.assertEqual(data['percentage'], 82)
        self.assertEqual(data['bar_width'], 82)
        self.assertEqual(data['bar_class'], 'bg-info')
        self.assertEqual(data['training_level_display'], 'Intermedio')
        # 80 kg ≥ novice (75) ma < intermediate (98)
        self.assertEqual(data['current_level'], 'novice')
        self.assertEqual(data['current_level_display'], 'Novizio')

    def test_uses_best_one_rm_not_latest(self):
        fill_profile(self.user)
        self.log(weight=98, reps=1)
        self.log(weight=60, reps=1)
        self.assertEqual(self.get().context['benchmark_data']['percentage'], 100)

    def test_progress_bar_capped_at_100(self):
        fill_profile(self.user)
        self.log(weight=150, reps=1)
        data = self.get().context['benchmark_data']
        self.assertEqual(data['percentage'], 153)
        self.assertEqual(data['bar_width'], 100)
        self.assertEqual(data['bar_class'], 'bg-success')
        self.assertEqual(data['current_level'], 'advanced')

    def test_below_first_level_has_no_current_level(self):
        fill_profile(self.user)
        self.log(weight=20, reps=1)
        data = self.get().context['benchmark_data']
        self.assertIsNone(data['current_level'])
        self.assertContains(self.get(), 'Sotto il livello Principiante')

    def test_age_lowers_target_and_level_thresholds(self):
        today = date.today()
        fill_profile(self.user, birth_date=date(today.year - 53, 1, 1))
        self.log(weight=90, reps=1)
        data = self.get().context['benchmark_data']
        self.assertEqual(data['benchmark_1rm'], 85.3)
        self.assertEqual(data['current_level'], 'intermediate')

    def test_other_users_logs_are_ignored(self):
        fill_profile(self.user)
        other = make_user('other')
        ExerciseLog.objects.create(
            user=other, exercise=self.exercise, date=date.today(),
            sets=1, reps=1, weight=200,
        )
        self.assertIsNone(self.get().context['benchmark_data']['percentage'])

    def test_logs_are_never_modified(self):
        fill_profile(self.user)
        log = self.log(weight=80, reps=5)
        log.refresh_from_db()
        before = (log.weight, log.reps, log.one_rm)
        self.get()
        log.refresh_from_db()
        self.assertEqual((log.weight, log.reps, log.one_rm), before)

    def test_card_rendered_with_data(self):
        fill_profile(self.user)
        self.log(weight=80, reps=1)
        response = self.get()
        self.assertContains(response, 'bi-trophy')
        self.assertContains(response, 'Target (Intermedio)')
        self.assertContains(response, '98,0 kg')


class StandardKeyMigrationTest(TestCase):
    """Il mapping della data migration riconosce i nomi del catalogo di partenza."""

    def test_seeded_names_are_mapped(self):
        import importlib
        migration = importlib.import_module('gym.migrations.0011_populate_standard_keys')
        by_name = {
            name: key for key, names in migration.MAPPING.items() for name in names
        }
        for seeded, expected in [
            ('Panca Piana', 'bench_press'),
            ('Stacco da Terra', 'deadlift'),
            ('Squat', 'squat'),
            ('Press Militare', 'overhead_press'),
            ('Rematore con Bilanciere', 'barbell_row'),
        ]:
            self.assertEqual(by_name[seeded.lower()], expected)

    def test_variants_are_not_mapped(self):
        import importlib
        migration = importlib.import_module('gym.migrations.0011_populate_standard_keys')
        names = {n for ns in migration.MAPPING.values() for n in ns}
        for variant in ('panca piana presa stretta', 'squat frontale', 'romanian deadlift'):
            self.assertNotIn(variant, names)

    def test_every_mapped_key_exists_in_standards(self):
        import importlib
        migration = importlib.import_module('gym.migrations.0011_populate_standard_keys')
        self.assertTrue(set(migration.MAPPING) <= set(ss.STANDARDS))


class ExerciseStandardKeyFormTest(TestCase):
    """Il collegamento esercizio → standard si gestisce dall'app, solo da admin."""

    def setUp(self):
        self.admin = User.objects.create_user('boss', password='pw', is_staff=True)
        self.author = make_user('author')
        self.exercise = Exercise.objects.create(
            name='Panca Larga', muscle_group=MuscleGroup.CHEST, created_by=self.author
        )

    def data(self, **extra):
        values = {'name': 'Panca Larga', 'muscle_group': MuscleGroup.CHEST}
        values.update(extra)
        return values

    def test_admin_sees_field_with_italian_labels(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('exercise_edit', args=[self.exercise.pk]))
        self.assertContains(response, 'Standard di forza')
        self.assertContains(response, 'Panca piana')
        self.assertContains(response, 'Nessuno')

    def test_regular_user_does_not_see_field(self):
        self.client.force_login(self.author)
        response = self.client.get(reverse('exercise_edit', args=[self.exercise.pk]))
        self.assertNotContains(response, 'Standard di forza')

    def test_admin_links_exercise(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse('exercise_edit', args=[self.exercise.pk]),
            self.data(standard_key='bench_press'),
        )
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.standard_key, 'bench_press')

    def test_admin_unlinks_with_none_stored_as_null(self):
        self.exercise.standard_key = 'bench_press'
        self.exercise.save()
        self.client.force_login(self.admin)
        self.client.post(
            reverse('exercise_edit', args=[self.exercise.pk]), self.data(standard_key='')
        )
        self.exercise.refresh_from_db()
        self.assertIsNone(self.exercise.standard_key)

    def test_invalid_key_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse('exercise_edit', args=[self.exercise.pk]),
            self.data(standard_key='inventato'),
        )
        self.assertEqual(response.status_code, 200)
        self.exercise.refresh_from_db()
        self.assertIsNone(self.exercise.standard_key)

    def test_regular_user_cannot_set_key_by_forging_post(self):
        self.client.force_login(self.author)
        self.client.post(
            reverse('exercise_edit', args=[self.exercise.pk]),
            self.data(standard_key='bench_press'),
        )
        self.exercise.refresh_from_db()
        self.assertIsNone(self.exercise.standard_key)

    def test_author_edit_keeps_link_set_by_admin(self):
        self.exercise.standard_key = 'bench_press'
        self.exercise.save()
        self.client.force_login(self.author)
        self.client.post(
            reverse('exercise_edit', args=[self.exercise.pk]),
            self.data(description='nuova descrizione'),
        )
        self.exercise.refresh_from_db()
        self.assertEqual(self.exercise.description, 'nuova descrizione')
        self.assertEqual(self.exercise.standard_key, 'bench_press')

    def test_admin_can_set_key_when_creating(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse('exercise_create'),
            self.data(name='Panca Olimpica', standard_key='bench_press'),
        )
        self.assertEqual(
            Exercise.objects.get(name='Panca Olimpica').standard_key, 'bench_press'
        )

    def test_list_marks_linked_exercises(self):
        self.client.force_login(self.author)
        self.assertNotContains(self.client.get(reverse('exercise_list')), 'bi-trophy')
        self.exercise.standard_key = 'squat'
        self.exercise.save()
        self.assertContains(self.client.get(reverse('exercise_list')), 'bi-trophy')

    def test_every_standard_has_a_label(self):
        self.assertEqual(set(ss.STANDARD_LABELS), set(ss.STANDARDS))


class MoreStandardKeysMigrationTest(TestCase):
    def setUp(self):
        import importlib
        self.migration = importlib.import_module(
            'gym.migrations.0013_populate_more_standard_keys'
        )
        self.first = importlib.import_module('gym.migrations.0011_populate_standard_keys')

    def test_every_mapped_key_exists_in_standards(self):
        self.assertTrue(set(self.migration.MAPPING) <= set(ss.STANDARDS))

    def test_all_standards_are_reachable_by_migrations(self):
        self.assertEqual(
            set(self.first.MAPPING) | set(self.migration.MAPPING), set(ss.STANDARDS)
        )

    def test_names_do_not_collide_between_migrations(self):
        names_a = {n for ns in self.first.MAPPING.values() for n in ns}
        names_b = {n for ns in self.migration.MAPPING.values() for n in ns}
        self.assertFalse(names_a & names_b)

    def test_populates_only_empty_keys(self):
        from django.apps import apps
        Exercise.objects.create(name='Hip Thrust', muscle_group=MuscleGroup.GLUTES)
        Exercise.objects.create(
            name='Squat Frontale', muscle_group=MuscleGroup.LEGS, standard_key='squat'
        )
        Exercise.objects.create(name='Leg Press', muscle_group=MuscleGroup.LEGS)

        self.migration.populate_standard_keys(apps, None)

        self.assertEqual(Exercise.objects.get(name='Hip Thrust').standard_key, 'hip_thrust')
        self.assertEqual(Exercise.objects.get(name='Squat Frontale').standard_key, 'squat')
        self.assertIsNone(Exercise.objects.get(name='Leg Press').standard_key)
