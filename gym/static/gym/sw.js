/**
 * GymIt — Service Worker
 * Cache-first per i file statici, network-first per le pagine Django.
 */

const CACHE_NAME = 'gymit-v1';

const STATIC_ASSETS = [
    '/static/gym/css/style.css',
    '/static/gym/js/main.js',
    '/static/gym/js/autocomplete.js',
    '/static/gym/js/dragdrop.js',
    '/static/gym/js/progress_chart.js',
];

// Installazione: pre-carica gli asset statici
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

// Attivazione: rimuove cache vecchie
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
            )
        )
    );
    self.clients.claim();
});

// Fetch: cache-first per statici, network-first per pagine
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Solo richieste GET
    if (event.request.method !== 'GET') return;

    // File statici: cache-first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(
            caches.match(event.request).then(
                (cached) => cached || fetch(event.request).then((response) => {
                    const clone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                    return response;
                })
            )
        );
        return;
    }

    // Pagine Django: network-first, fallback offline minimale
    event.respondWith(
        fetch(event.request).catch(() =>
            new Response(
                '<html><body style="background:#0d0d0d;color:#fff;font-family:sans-serif;text-align:center;padding:2rem">' +
                '<h2>⚡ GymIt</h2><p>Connessione assente. Riconnettiti per continuare.</p></body></html>',
                { headers: { 'Content-Type': 'text/html' } }
            )
        )
    );
});
