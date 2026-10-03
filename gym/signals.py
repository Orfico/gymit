from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, raw=False, **kwargs):
    """Ogni nuovo utente nasce con un profilo fisico vuoto."""
    # `raw` è vero durante il caricamento di fixture: lì i dati arrivano già
    # completi (profilo compreso) e crearne uno qui provocherebbe un duplicato.
    if created and not raw:
        UserProfile.objects.get_or_create(user=instance)
