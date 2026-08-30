"""
Promuove ad amministratore l'utente che gestisce i video tutorial.

Parametrica di proposito: il nome utente arriva da `ADMIN_USERNAME` (default
`Luca`) perché nel database non esiste un account con quel nome — gli account
presenti sono altri e senza email — quindi non c'era modo di identificarlo con
certezza a priori. Se l'utente non c'è la migration non fallisce: registra un
avviso e prosegue, così un deploy non si blocca per un dato di ambiente.
"""

import logging
import os

from django.db import migrations

logger = logging.getLogger(__name__)

DEFAULT_ADMIN_USERNAME = 'Luca'


def promote_admin(apps, schema_editor):
    """
    Idempotente: se l'utente è già staff non tocca nulla, quindi rieseguirla
    (o rieseguire l'intera migrazione) non ha effetti collaterali.
    """
    User = apps.get_model('auth', 'User')

    identifier = os.environ.get('ADMIN_USERNAME', DEFAULT_ADMIN_USERNAME).strip()
    if not identifier:
        logger.warning(
            'ADMIN_USERNAME vuoto: nessun utente promosso ad amministratore.'
        )
        return

    # Si accetta anche un'email, perché l'utente da promuovere potrebbe essere
    # identificato dall'una o dall'altra a seconda di come è stato creato.
    user = (
        User.objects.filter(username__iexact=identifier).first()
        or User.objects.filter(email__iexact=identifier).first()
    )

    if user is None:
        logger.warning(
            'Nessun utente corrisponde a "%s": nessuna promozione effettuata. '
            'Imposta la variabile ADMIN_USERNAME con lo username (o l\'email) '
            'corretto ed esegui di nuovo la migrazione, oppure assegna il flag '
            'staff dal pannello di amministrazione.',
            identifier,
        )
        return

    if user.is_staff:
        logger.info(
            'Utente "%s" è già amministratore: nessuna modifica.', user.username
        )
        return

    user.is_staff = True
    user.save(update_fields=['is_staff'])
    logger.info(
        'Utente "%s" promosso ad amministratore: può gestire i video tutorial.',
        user.username,
    )


def noop_reverse(apps, schema_editor):
    """
    Tornare indietro non revoca i permessi: il flag potrebbe essere stato messo
    a mano dopo questa migrazione, e toglierlo rischierebbe di lasciare
    l'installazione senza amministratori.
    """
    logger.info(
        'Rollback di 0008: i permessi di amministratore vengono lasciati '
        'invariati di proposito.'
    )


class Migration(migrations.Migration):

    dependencies = [
        ('gym', '0007_exercise_video_added_at_exercise_video_added_by_and_more'),
    ]

    operations = [
        migrations.RunPython(promote_admin, noop_reverse),
    ]
