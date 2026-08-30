"""Valori disponibili in ogni template."""

from .models import shows_video_admin as _shows_video_admin


def video_admin_preference(request):
    """
    L'interruttore degli strumenti video vive nel menu utente, quindi in
    ogni pagina: serve un context processor, non il contesto della singola
    vista. Per chi non è staff la funzione esce subito senza query.
    """
    return {'shows_video_admin': _shows_video_admin(request.user)}
