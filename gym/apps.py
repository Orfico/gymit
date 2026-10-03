from django.apps import AppConfig


class GymConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gym'
    verbose_name = 'GymIt'

    def ready(self):
        from . import signals  # noqa: F401  (registra i receiver)
