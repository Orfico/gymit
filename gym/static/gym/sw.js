/**
 * GymIt — Service Worker
 * 
 * Strategia:
 * - Static assets: cache-first con runtime caching
 * - Pagine HTML: network-first con cache fallback
 * - POST / API mutation: network-only
 * 
 * Incrementa CACHE_VERSION ad ogni deploy per invalidare la cache.
 */

const CACHE_VERSION = 'gymit-v3';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const PAGES_CACHE  = `${CACHE_VERSION}-pages`;

const ALL_CACHES = [STATIC_CACHE, PAGES_CACHE];

// Pagine da pre-cachare all'installazione
const PRECACHE_PAGES = [
    '/',
    '/plans/',
    '/progress/',
    '/exercises/',
];

// Pattern URL che non vanno mai cachati
const NEVER_CACHE = [
    /\/users\/login/,
    /\/users\/logout/,
    /\/users\/register/,
    /\/exercises\/autocomplete/,
    /\/plans\/reorder/,
    /\/planned\/\d+\/remove/,
    /\/log\/\d+\/delete/,
    /\/plans\/\d+\/reorder/,
    /\/sw\.js/,
];

function shouldNeverCache(url) {
    return NEVER_CACHE.some(pattern => pattern.test(url.pathname));
}

// ── Installazione ─────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(PAGES_CACHE).then((cache) =>
            cache.addAll(PRECACHE_PAGES).catch(() => {
                // Se offline durante l'installazione, ignora silenziosamente
            })
        )
    );
    self.skipWaiting();
});

// ── Attivazione — rimuove cache vecchie ──────────────────────────────────────
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(
                keys
                    .filter((key) => !ALL_CACHES.includes(key))
                    .map((key) => caches.delete(key))
            )
        )
    );
    self.clients.claim();
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Solo stesso dominio, solo GET
    if (request.method !== 'GET') return;
    if (url.origin !== self.location.origin) return;
    if (shouldNeverCache(url)) return;

    // File statici: cache-first
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(cacheFirst(request, STATIC_CACHE));
        return;
    }

    // Pagine HTML: network-first con cache fallback
    if (request.headers.get('accept')?.includes('text/html')) {
        event.respondWith(networkFirstWithCache(request, PAGES_CACHE));
        return;
    }
});

// ── Strategie ─────────────────────────────────────────────────────────────────

async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) return cached;
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        return new Response('', { status: 408 });
    }
}

async function networkFirstWithCache(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch {
        const cached = await caches.match(request);
        if (cached) return cached;

        // Fallback pagina offline
        return new Response(`
            <!DOCTYPE html>
            <html lang="it">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>GymIt — Offline</title>
                <style>
                    body { background:#0d0d0d; color:#f8f9fa; font-family:sans-serif;
                           display:flex; align-items:center; justify-content:center;
                           min-height:100vh; margin:0; text-align:center; padding:2rem; }
                    h2 { color:#ffc107; }
                    p  { color:#adb5bd; }
                    a  { color:#ffc107; }
                </style>
            </head>
            <body>
                <div>
                    <h2>⚡ GymIt</h2>
                    <p>Sei offline e questa pagina non è ancora in cache.</p>
                    <p><a href="/">Torna alla home</a></p>
                </div>
            </body>
            </html>
        `, { headers: { 'Content-Type': 'text/html' } });
    }
}