"""
Riconoscimento e verifica dei link YouTube.

Modulo a sé perché è logica pura (più una singola chiamata di rete) che non
appartiene né alle viste né ai form: si presta a essere testata da sola, ed è
il punto in cui si concentra la regola di sicurezza più importante della
feature — dall'input dell'utente si estrae **solo** un identificativo di 11
caratteri, e da quello si ricostruiscono lato server gli URL usati nel markup.
L'URL incollato non finisce mai in un attributo `src`.
"""

import logging
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Host accettati. `youtu.be` è il dominio breve, `youtube-nocookie.com` compare
# quando si incolla un embed già "privacy enhanced".
YOUTUBE_HOSTS = frozenset({
    'youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com',
    'youtu.be', 'www.youtu.be',
    'youtube-nocookie.com', 'www.youtube-nocookie.com',
})

# Un id YouTube è esattamente questo: 11 caratteri dell'alfabeto base64-url.
VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')

THUMBNAIL_URL = 'https://img.youtube.com/vi/{video_id}/hqdefault.jpg'
EMBED_URL = 'https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1'
WATCH_URL = 'https://www.youtube.com/watch?v={video_id}'

VERIFY_TIMEOUT_SECONDS = 3


def extract_video_id(raw_url):
    """
    Estrae l'id canonico da un URL YouTube, in qualunque forma sia stato
    incollato. Restituisce None se il link non è YouTube o se l'id non ha la
    forma attesa: chi chiama tratta None come "rifiuta".

    I parametri di troppo (`&t=`, `&si=`, ...) vengono semplicemente ignorati,
    perché si legge solo la parte che identifica il video.
    """
    raw_url = (raw_url or '').strip()
    if not raw_url:
        return None

    # Tollerante sullo schema mancante ("youtu.be/xxx" copiato a mano), ma
    # senza inventarsi nulla: quello che conta resta host + percorso.
    if '//' not in raw_url:
        raw_url = 'https://' + raw_url

    try:
        parsed = urlparse(raw_url)
    except ValueError:
        return None

    if parsed.scheme not in ('http', 'https'):
        return None

    host = (parsed.hostname or '').lower()
    if host not in YOUTUBE_HOSTS:
        return None

    path = parsed.path or ''

    if host in ('youtu.be', 'www.youtu.be'):
        candidate = path.lstrip('/').split('/')[0]
    elif path == '/watch' or path.startswith('/watch/'):
        candidate = parse_qs(parsed.query).get('v', [''])[0]
    elif path.startswith('/shorts/'):
        candidate = path[len('/shorts/'):].split('/')[0]
    elif path.startswith('/embed/'):
        candidate = path[len('/embed/'):].split('/')[0]
    elif path.startswith('/live/'):
        candidate = path[len('/live/'):].split('/')[0]
    else:
        return None

    candidate = candidate.strip()
    return candidate if VIDEO_ID_RE.match(candidate) else None


def video_exists(video_id, timeout=VERIFY_TIMEOUT_SECONDS):
    """
    Verifica che il video esista chiedendo la sua copertina.

    Tre esiti distinti, perché "non esiste" e "non sono riuscito a
    controllare" non vanno confusi:
      True  — la copertina c'è, il video esiste
      False — 404, video rimosso o privato: va rifiutato
      None  — rete non disponibile o errore lato YouTube: non si può sapere,
              chi chiama lascia passare invece di bloccare l'admin per un
              problema che non dipende da lui.

    Si usa la copertina invece delle API ufficiali per non introdurre chiave,
    quota e dipendenze.
    """
    if not VIDEO_ID_RE.match(video_id or ''):
        return False

    url = THUMBNAIL_URL.format(video_id=video_id)
    try:
        with urlopen(Request(url, method='HEAD'), timeout=timeout) as response:
            return 200 <= response.status < 300
    except HTTPError as exc:
        if exc.code == 404:
            return False
        # 403/5xx dicono qualcosa su YouTube, non sull'esistenza del video.
        logger.warning('Verifica video %s: HTTP %s', video_id, exc.code)
        return None
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning('Verifica video %s non riuscita: %s', video_id, exc)
        return None


def thumbnail_url(video_id):
    return THUMBNAIL_URL.format(video_id=video_id)


def embed_url(video_id):
    """URL di embed sul dominio senza cookie, costruito solo dall'id."""
    return EMBED_URL.format(video_id=video_id)


def watch_url(video_id):
    return WATCH_URL.format(video_id=video_id)
