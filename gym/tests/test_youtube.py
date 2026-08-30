"""Parsing dei link YouTube e verifica di esistenza del video."""

from unittest.mock import patch
from urllib.error import HTTPError, URLError

from django.test import TestCase

from gym import youtube


class ExtractVideoIdTest(TestCase):
    VALID_ID = 'dQw4w9WgXcQ'

    def test_watch_url(self):
        self.assertEqual(
            youtube.extract_video_id(f'https://www.youtube.com/watch?v={self.VALID_ID}'),
            self.VALID_ID,
        )

    def test_short_url(self):
        self.assertEqual(
            youtube.extract_video_id(f'https://youtu.be/{self.VALID_ID}'),
            self.VALID_ID,
        )

    def test_shorts_url(self):
        self.assertEqual(
            youtube.extract_video_id(f'https://www.youtube.com/shorts/{self.VALID_ID}'),
            self.VALID_ID,
        )

    def test_mobile_url(self):
        self.assertEqual(
            youtube.extract_video_id(f'https://m.youtube.com/watch?v={self.VALID_ID}'),
            self.VALID_ID,
        )

    def test_music_url(self):
        self.assertEqual(
            youtube.extract_video_id(f'https://music.youtube.com/watch?v={self.VALID_ID}'),
            self.VALID_ID,
        )

    def test_embed_url(self):
        self.assertEqual(
            youtube.extract_video_id(f'https://www.youtube.com/embed/{self.VALID_ID}'),
            self.VALID_ID,
        )

    def test_nocookie_embed_url(self):
        self.assertEqual(
            youtube.extract_video_id(
                f'https://www.youtube-nocookie.com/embed/{self.VALID_ID}'
            ),
            self.VALID_ID,
        )

    def test_live_url(self):
        self.assertEqual(
            youtube.extract_video_id(f'https://www.youtube.com/live/{self.VALID_ID}'),
            self.VALID_ID,
        )

    # ── Parametri in coda ────────────────────────────────────────────
    def test_watch_url_with_timestamp(self):
        self.assertEqual(
            youtube.extract_video_id(
                f'https://www.youtube.com/watch?v={self.VALID_ID}&t=42s'
            ),
            self.VALID_ID,
        )

    def test_watch_url_with_list_and_index(self):
        self.assertEqual(
            youtube.extract_video_id(
                f'https://www.youtube.com/watch?v={self.VALID_ID}&list=PL123&index=2'
            ),
            self.VALID_ID,
        )

    def test_short_url_with_si_parameter(self):
        self.assertEqual(
            youtube.extract_video_id(f'https://youtu.be/{self.VALID_ID}?si=AbCdEf'),
            self.VALID_ID,
        )

    def test_shorts_url_with_feature_parameter(self):
        self.assertEqual(
            youtube.extract_video_id(
                f'https://www.youtube.com/shorts/{self.VALID_ID}?feature=share'
            ),
            self.VALID_ID,
        )

    def test_watch_url_with_v_not_first(self):
        self.assertEqual(
            youtube.extract_video_id(
                f'https://www.youtube.com/watch?t=10&v={self.VALID_ID}'
            ),
            self.VALID_ID,
        )

    # ── Tolleranze ───────────────────────────────────────────────────
    def test_http_scheme_accepted(self):
        self.assertEqual(
            youtube.extract_video_id(f'http://www.youtube.com/watch?v={self.VALID_ID}'),
            self.VALID_ID,
        )

    def test_missing_scheme_accepted(self):
        self.assertEqual(
            youtube.extract_video_id(f'youtu.be/{self.VALID_ID}'),
            self.VALID_ID,
        )

    def test_surrounding_whitespace_ignored(self):
        self.assertEqual(
            youtube.extract_video_id(f'  https://youtu.be/{self.VALID_ID}  '),
            self.VALID_ID,
        )

    def test_uppercase_host_accepted(self):
        self.assertEqual(
            youtube.extract_video_id(f'https://WWW.YOUTUBE.COM/watch?v={self.VALID_ID}'),
            self.VALID_ID,
        )

    # ── Rifiuti ──────────────────────────────────────────────────────
    def test_non_youtube_host_rejected(self):
        self.assertIsNone(
            youtube.extract_video_id(f'https://vimeo.com/watch?v={self.VALID_ID}')
        )

    def test_lookalike_host_rejected(self):
        """Un dominio che *contiene* youtube.com non è youtube.com."""
        self.assertIsNone(
            youtube.extract_video_id(f'https://youtube.com.evil.example/watch?v={self.VALID_ID}')
        )

    def test_javascript_scheme_rejected(self):
        self.assertIsNone(youtube.extract_video_id('javascript:alert(1)'))

    def test_id_too_short_rejected(self):
        self.assertIsNone(youtube.extract_video_id('https://youtu.be/abc'))

    def test_id_too_long_rejected(self):
        self.assertIsNone(youtube.extract_video_id('https://youtu.be/' + 'a' * 12))

    def test_id_with_invalid_characters_rejected(self):
        self.assertIsNone(youtube.extract_video_id('https://youtu.be/abcdefghij!'))

    def test_watch_without_v_parameter_rejected(self):
        self.assertIsNone(youtube.extract_video_id('https://www.youtube.com/watch?t=10'))

    def test_channel_url_rejected(self):
        self.assertIsNone(youtube.extract_video_id('https://www.youtube.com/@qualcuno'))

    def test_homepage_rejected(self):
        self.assertIsNone(youtube.extract_video_id('https://www.youtube.com/'))

    def test_empty_input_rejected(self):
        self.assertIsNone(youtube.extract_video_id(''))

    def test_none_input_rejected(self):
        self.assertIsNone(youtube.extract_video_id(None))

    def test_plain_text_rejected(self):
        self.assertIsNone(youtube.extract_video_id('non è un link'))

    def test_bare_video_id_rejected(self):
        """Si accettano link, non identificativi nudi: meno margine di errore."""
        self.assertIsNone(youtube.extract_video_id(self.VALID_ID))

    def test_non_http_scheme_rejected(self):
        self.assertIsNone(
            youtube.extract_video_id(f'ftp://www.youtube.com/watch?v={self.VALID_ID}')
        )

    def test_unparsable_url_rejected_without_raising(self):
        """Un URL malformato deve tornare None, non far esplodere la vista."""
        self.assertIsNone(youtube.extract_video_id('https://[::1/watch?v=x'))
        self.assertIsNone(youtube.extract_video_id('https://[oops]/watch'))

    def test_invalid_port_does_not_crash(self):
        """La porta non viene mai usata: conta solo che l'host sia YouTube."""
        self.assertEqual(
            youtube.extract_video_id(
                f'https://www.youtube.com:porta/watch?v={self.VALID_ID}'
            ),
            self.VALID_ID,
        )


class VideoExistsTest(TestCase):
    VALID_ID = 'dQw4w9WgXcQ'

    class _FakeResponse:
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def test_returns_true_on_200(self):
        with patch('gym.youtube.urlopen', return_value=self._FakeResponse(200)):
            self.assertIs(youtube.video_exists(self.VALID_ID), True)

    def test_returns_false_on_404(self):
        error = HTTPError('url', 404, 'Not Found', {}, None)
        with patch('gym.youtube.urlopen', side_effect=error):
            self.assertIs(youtube.video_exists(self.VALID_ID), False)

    def test_returns_none_on_server_error(self):
        """Un 500 parla di YouTube, non del video: esito indeterminato."""
        error = HTTPError('url', 503, 'Service Unavailable', {}, None)
        with patch('gym.youtube.urlopen', side_effect=error):
            self.assertIsNone(youtube.video_exists(self.VALID_ID))

    def test_returns_none_on_timeout(self):
        with patch('gym.youtube.urlopen', side_effect=TimeoutError('timeout')):
            self.assertIsNone(youtube.video_exists(self.VALID_ID))

    def test_returns_none_on_connection_error(self):
        with patch('gym.youtube.urlopen', side_effect=URLError('offline')):
            self.assertIsNone(youtube.video_exists(self.VALID_ID))

    def test_malformed_id_rejected_without_network_call(self):
        with patch('gym.youtube.urlopen') as mocked:
            self.assertIs(youtube.video_exists('troppo-corto'), False)
        mocked.assert_not_called()

    def test_uses_thumbnail_endpoint_with_head(self):
        with patch('gym.youtube.urlopen', return_value=self._FakeResponse(200)) as mocked:
            youtube.video_exists(self.VALID_ID)
        request = mocked.call_args[0][0]
        self.assertEqual(request.get_method(), 'HEAD')
        self.assertEqual(
            request.full_url,
            f'https://img.youtube.com/vi/{self.VALID_ID}/hqdefault.jpg',
        )

    def test_timeout_is_three_seconds(self):
        with patch('gym.youtube.urlopen', return_value=self._FakeResponse(200)) as mocked:
            youtube.video_exists(self.VALID_ID)
        self.assertEqual(mocked.call_args.kwargs['timeout'], 3)


class UrlBuildersTest(TestCase):
    VALID_ID = 'dQw4w9WgXcQ'

    def test_embed_url_uses_nocookie_domain(self):
        url = youtube.embed_url(self.VALID_ID)
        self.assertTrue(url.startswith('https://www.youtube-nocookie.com/embed/'))
        self.assertIn(self.VALID_ID, url)
        self.assertNotIn('//www.youtube.com', url)

    def test_embed_url_disables_related_and_branding(self):
        url = youtube.embed_url(self.VALID_ID)
        self.assertIn('rel=0', url)
        self.assertIn('modestbranding=1', url)

    def test_thumbnail_url(self):
        self.assertEqual(
            youtube.thumbnail_url(self.VALID_ID),
            f'https://img.youtube.com/vi/{self.VALID_ID}/hqdefault.jpg',
        )

    def test_watch_url(self):
        self.assertEqual(
            youtube.watch_url(self.VALID_ID),
            f'https://www.youtube.com/watch?v={self.VALID_ID}',
        )
