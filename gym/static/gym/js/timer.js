/**
 * GymIt — Timer di recupero (widget globale floating)
 *
 * Tutto lato client. Lo stato (durata, secondi rimanenti, timestamp di
 * fine) vive in sessionStorage così sopravvive alla navigazione tra
 * pagine (ogni pagina è un caricamento pieno, non una SPA): ad ogni
 * load il countdown viene ricalcolato dal timestamp assoluto, non da
 * un contatore di tick — questo lo rende corretto anche se il tab è
 * stato in background/il telefono in standby e i tick sono stati
 * sospesi dal browser nel frattempo.
 *
 * Limite di piattaforma: mentre lo schermo è bloccato o il tab non è
 * visibile, i browser sospendono l'esecuzione JS — non è possibile far
 * vibrare il telefono esattamente allo scadere. Vibrazione/beep/pulse
 * partono non appena la pagina torna visibile, con il countdown già
 * corretto.
 */

(function () {
    var STORAGE_KEY = 'gymit_rest_timer_state';
    var LAST_DURATION_KEY = 'gymit_rest_timer_last_duration';
    var DEFAULT_DURATION = 90;
    var MIN_DURATION = 5;
    var MAX_DURATION = 900;
    var FINISHED_FLASH_MS = 3000;
    var TICK_MS = 250;

    var widget = document.getElementById('restTimerWidget');
    if (!widget) return; // utente non autenticato: il markup non esiste in questa pagina

    var fab = document.getElementById('restTimerFab');
    var ring = widget.querySelector('.rest-timer-fab-ring');
    var fabSeconds = widget.querySelector('.rest-timer-fab-seconds');
    var panel = document.getElementById('restTimerPanel');
    var closeBtn = document.getElementById('restTimerClose');
    var display = document.getElementById('restTimerDisplay');
    var progressBar = document.getElementById('restTimerProgressBar');
    var presetButtons = widget.querySelectorAll('.rest-timer-preset');
    var customInput = document.getElementById('restTimerCustomInput');
    var toggleBtn = document.getElementById('restTimerToggle');
    var resetBtn = document.getElementById('restTimerReset');

    var state = null;
    var audioCtx = null;
    var tickHandle = null;

    // ── Audio beep (fallback/complemento alla vibrazione — su iOS
    // navigator.vibrate non esiste affatto) ─────────────────────────
    function unlockAudio() {
        if (audioCtx) return;
        var Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        try { audioCtx = new Ctx(); } catch (e) { /* ignore */ }
    }

    function beep(delayMs, freq) {
        if (!audioCtx) return;
        if (audioCtx.state === 'suspended') audioCtx.resume().catch(function () {});
        setTimeout(function () {
            try {
                var osc = audioCtx.createOscillator();
                var gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.frequency.value = freq || 880;
                var now = audioCtx.currentTime;
                gain.gain.setValueAtTime(0.0001, now);
                gain.gain.exponentialRampToValueAtTime(0.3, now + 0.02);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.5);
                osc.connect(gain).connect(audioCtx.destination);
                osc.start(now);
                osc.stop(now + 0.55);
            } catch (e) { /* AudioContext non disponibile/bloccato */ }
        }, delayMs || 0);
    }

    function notifyFinished() {
        try { if (navigator.vibrate) navigator.vibrate([200, 100, 200]); } catch (e) { /* ignore */ }
        beep(0, 880);
        beep(300, 880);
    }

    // Sblocca l'AudioContext al primo gesto utente su QUALSIASI parte
    // della pagina (non solo sul widget) — se il timer termina mentre
    // l'utente sta usando un'altra pagina, deve bastare un tocco
    // qualsiasi prima dello scadere per abilitare il beep.
    ['pointerdown', 'keydown'].forEach(function (evt) {
        document.addEventListener(evt, unlockAudio, { once: true, passive: true });
    });

    // ── Stato ─────────────────────────────────────────────────────
    function defaultDuration() {
        var last = parseInt(localStorage.getItem(LAST_DURATION_KEY), 10);
        if (last && last >= MIN_DURATION && last <= MAX_DURATION) return last;
        return DEFAULT_DURATION;
    }

    function loadState() {
        var raw = sessionStorage.getItem(STORAGE_KEY);
        if (raw) {
            try {
                var parsed = JSON.parse(raw);
                if (parsed && typeof parsed.duration === 'number') return parsed;
            } catch (e) { /* stato corrotto: ignora e ricrea */ }
        }
        var d = defaultDuration();
        return { duration: d, remaining: d, status: 'idle', endAt: null, finishedAt: null, notified: false };
    }

    function saveState() {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }

    function rememberDuration(seconds) {
        localStorage.setItem(LAST_DURATION_KEY, String(seconds));
    }

    // ── Calcolo tempo rimanente ──────────────────────────────────
    function computeRemaining() {
        if (state.status === 'running') {
            return Math.max(0, (state.endAt - Date.now()) / 1000);
        }
        return state.remaining;
    }

    // ── Transizioni ───────────────────────────────────────────────
    function start(seconds) {
        if (typeof seconds === 'number') {
            state.duration = seconds;
            rememberDuration(seconds);
        }
        var startFrom = (state.status === 'paused') ? state.remaining : state.duration;
        state.status = 'running';
        state.endAt = Date.now() + startFrom * 1000;
        state.finishedAt = null;
        state.notified = false;
        saveState();
        render();
    }

    function pause() {
        if (state.status !== 'running') return;
        state.remaining = computeRemaining();
        state.status = 'paused';
        state.endAt = null;
        saveState();
        render();
    }

    function reset() {
        state.status = 'idle';
        state.remaining = state.duration;
        state.endAt = null;
        state.finishedAt = null;
        state.notified = false;
        saveState();
        render();
    }

    function applyPreset(seconds) {
        // Imposta la durata e avvia subito — meno tap tra una serie e l'altra.
        state.duration = seconds;
        state.remaining = seconds;
        rememberDuration(seconds);
        start(seconds);
    }

    function finish() {
        state.status = 'finished';
        state.remaining = 0;
        state.endAt = null;
        state.finishedAt = Date.now();
        if (!state.notified) {
            state.notified = true;
            notifyFinished();
        }
        saveState();
        render();
    }

    // ── Rendering ─────────────────────────────────────────────────
    function formatMMSS(totalSeconds) {
        var s = Math.max(0, Math.round(totalSeconds));
        var m = Math.floor(s / 60);
        var r = s % 60;
        return (m < 10 ? '0' + m : m) + ':' + (r < 10 ? '0' + r : r);
    }

    function render() {
        var remaining = computeRemaining();
        var duration = state.duration || 1;
        var fraction = Math.max(0, Math.min(1, remaining / duration));

        display.textContent = formatMMSS(remaining);
        progressBar.style.width = (fraction * 100) + '%';
        ring.style.setProperty('--ring', fraction);
        fabSeconds.textContent = String(Math.max(0, Math.ceil(remaining)));

        var active = state.status === 'running' || state.status === 'paused';
        var finished = state.status === 'finished';
        widget.classList.toggle('is-active', active);
        widget.classList.toggle('is-finished', finished);

        if (state.status === 'running') {
            toggleBtn.innerHTML = '<i class="bi bi-pause-fill"></i> Pausa';
        } else {
            toggleBtn.innerHTML = '<i class="bi bi-play-fill"></i> Avvia';
        }

        presetButtons.forEach(function (btn) {
            var seconds = parseInt(btn.dataset.seconds, 10);
            btn.classList.toggle('active', seconds === state.duration);
        });

        fab.setAttribute('aria-label', active || finished
            ? 'Timer di recupero, ' + Math.ceil(remaining) + ' secondi rimanenti'
            : 'Timer di recupero');
    }

    // ── Ciclo di aggiornamento ──────────────────────────────────────
    function tick() {
        if (state.status === 'running') {
            if (computeRemaining() <= 0) {
                finish();
                return;
            }
            render();
        } else if (state.status === 'finished') {
            if (Date.now() - state.finishedAt >= FINISHED_FLASH_MS) {
                reset();
            }
        }
    }

    function startTicking() {
        if (tickHandle) clearInterval(tickHandle);
        tickHandle = setInterval(tick, TICK_MS);
    }

    // Ricalcola subito appena la pagina torna visibile/attiva, così un
    // countdown scaduto mentre eravamo in background/standby si
    // aggiorna (e notifica) immediatamente al rientro invece di
    // aspettare il prossimo tick "naturale".
    document.addEventListener('visibilitychange', function () {
        if (document.visibilityState === 'visible') tick();
    });
    window.addEventListener('focus', tick);
    window.addEventListener('pageshow', function (e) {
        if (e.persisted) tick(); // rientro dalla bfcache
    });

    // ── Pannello aperto/chiuso ───────────────────────────────────────
    function openPanel() {
        panel.hidden = false;
        unlockAudio();
    }
    function closePanel() {
        panel.hidden = true;
    }

    fab.addEventListener('click', function () {
        unlockAudio();
        if (panel.hidden) openPanel();
        else closePanel();
    });
    closeBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        closePanel();
    });

    // Click fuori dal widget chiude il pannello (ma non ferma il timer).
    document.addEventListener('click', function (e) {
        if (!panel.hidden && !widget.contains(e.target)) closePanel();
    });

    // ── Controlli ─────────────────────────────────────────────────
    presetButtons.forEach(function (btn) {
        btn.addEventListener('click', function () {
            applyPreset(parseInt(btn.dataset.seconds, 10));
        });
    });

    function applyCustomDuration() {
        var seconds = parseInt(customInput.value, 10);
        if (!seconds || isNaN(seconds)) return;
        seconds = Math.max(MIN_DURATION, Math.min(MAX_DURATION, seconds));
        customInput.value = '';
        applyPreset(seconds);
    }

    customInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') applyCustomDuration();
    });
    customInput.addEventListener('blur', applyCustomDuration);
    customInput.addEventListener('change', applyCustomDuration);

    toggleBtn.addEventListener('click', function () {
        if (state.status === 'running') pause();
        else start();
    });

    resetBtn.addEventListener('click', reset);

    // ── Init ──────────────────────────────────────────────────────
    state = loadState();
    // Se lo stato salvato indica un countdown già scaduto (es. la pagina
    // è stata ricaricata a timer terminato) risolviamolo subito.
    if (state.status === 'running' && computeRemaining() <= 0) {
        finish();
    } else if (state.status === 'finished' && Date.now() - state.finishedAt >= FINISHED_FLASH_MS) {
        reset();
    } else {
        render();
    }
    startTicking();
})();
