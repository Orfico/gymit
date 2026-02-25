/**
 * GymIt — Service Worker
 * Network-first per tutto: nessun pre-caching di file statici
 * per evitare conflitti con i nomi hashati di WhiteNoise.
 */

const CACHE_NAME = 'gymit-v2';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.map((key) => caches.delete(key)))
        )
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    // Solo richieste GET
    if (event.request.method !== 'GET') return;

    // Network-first: prova la rete, fallback offline minimale solo per navigazione
    event.respondWith(
        fetch(event.request).catch(() => {
            // Fallback solo per richieste di navigazione (pagine HTML)
            if (event.request.mode === 'navigate') {
                return new Response(
                    '<html><body style="background:#0d0d0d;color:#fff;font-family:sans-serif;text-align:center;padding:2rem">' +
                    '<h2>⚡ GymIt</h2><p>Connessione assente. Riconnettiti per continuare.</p></body></html>',
                    { headers: { 'Content-Type': 'text/html' } }
                );
            }
        })
    );
});