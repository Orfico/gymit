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
 *
 * Allo scadere il timer entra in stato "finished" e resta lì — niente
 * timeout automatico: suono e vibrazione continuano a ripetersi finché
 * l'utente non tocca il FAB per interromperli (nessun bisogno di aprire
 * il pannello). Lo stato "finished" persiste anche attraverso la
 * navigazione tra pagine, quindi l'allarme riprende a suonare se non è
 * ancora stato interrotto.
 */

(function () {
    var STORAGE_KEY = 'gymit_rest_timer_state';
    var LAST_DURATION_KEY = 'gymit_rest_timer_last_duration';
    var DEFAULT_DURATION = 90;
    var MIN_DURATION = 5;
    var MAX_DURATION = 900;
    var TICK_MS = 250;
    var ALARM_REPEAT_MS = 1100;

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
    var alarmIntervalId = null;

    // ── Audio allarme (fallback/complemento alla vibrazione — su iOS
    // navigator.vibrate non esiste affatto). Onda quadra + guadagno alto:
    // più penetrante di un sine, per farsi notare anche in un ambiente
    // rumoroso come una palestra. Si ripete finché non viene interrotto.
    function unlockAudio() {
        if (audioCtx) return;
        var Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        try { audioCtx = new Ctx(); } catch (e) { /* ignore */ }
    }

    function tone(startAt, freq) {
        var osc = audioCtx.createOscillator();
        var gain = audioCtx.createGain();
        osc.type = 'square';
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, startAt);
        gain.gain.exponentialRampToValueAtTime(0.55, startAt + 0.03);
        gain.gain.exponentialRampToValueAtTime(0.0001, startAt + 0.32);
        osc.connect(gain).connect(audioCtx.destination);
        osc.start(startAt);
        osc.stop(startAt + 0.34);
    }

    function playAlarmBurst() {
        if (!audioCtx) return;
        if (audioCtx.state === 'suspended') audioCtx.resume().catch(function () {});
        try {
            var now = audioCtx.currentTime;
            tone(now, 988); // B5
            tone(now + 0.38, 1318); // E6 — coppia di toni tipo sveglia da cucina
        } catch (e) { /* AudioContext non disponibile/bloccato */ }
    }

    function startAlarmLoop() {
        if (alarmIntervalId) return; // già in corso
        var fire = function () {
            try { if (navigator.vibrate) navigator.vibrate([300, 100, 300]); } catch (e) { /* ignore */ }
            playAlarmBurst();
        };
        fire();
        alarmIntervalId = setInterval(fire, ALARM_REPEAT_MS);
    }

    function stopAlarm() {
        if (!alarmIntervalId) return;
        clearInterval(alarmIntervalId);
        alarmIntervalId = null;
        try { if (navigator.vibrate) navigator.vibrate(0); } catch (e) { /* ignore */ }
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
        return { duration: d, remaining: d, status: 'idle', endAt: null, finishedAt: null };
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
        stopAlarm();
        if (typeof seconds === 'number') {
            state.duration = seconds;
            rememberDuration(seconds);
        }
        var startFrom = (state.status === 'paused') ? state.remaining : state.duration;
        state.status = 'running';
        state.endAt = Date.now() + startFrom * 1000;
        state.finishedAt = null;
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
        stopAlarm();
        state.status = 'idle';
        state.remaining = state.duration;
        state.endAt = null;
        state.finishedAt = null;
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
        saveState();
        render();
        startAlarmLoop();
    }

    // L'utente interrompe l'allarme toccando il FAB — non serve aprire
    // il pannello. Torna direttamente a idle, pronto per un nuovo giro.
    function dismissFinished() {
        stopAlarm();
        reset();
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

        var label = 'Timer di recupero';
        if (finished) label = 'Timer di recupero terminato, tocca per interrompere l\'allarme';
        else if (active) label = 'Timer di recupero, ' + Math.ceil(remaining) + ' secondi rimanenti';
        fab.setAttribute('aria-label', label);
    }

    // ── Ciclo di aggiornamento ──────────────────────────────────────
    function tick() {
        if (state.status !== 'running') return;
        if (computeRemaining() <= 0) {
            finish();
        } else {
            render();
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
        if (state.status === 'finished') {
            dismissFinished();
            return;
        }
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
    if (state.status === 'running' && computeRemaining() <= 0) {
        // Countdown già scaduto (es. la pagina è stata ricaricata a timer
        // terminato): passa subito a "finished" e fai partire l'allarme.
        finish();
    } else if (state.status === 'finished') {
        // L'allarme non è ancora stato interrotto dall'utente: riprende
        // a suonare anche su questa pagina.
        render();
        startAlarmLoop();
    } else {
        render();
    }
    startTicking();
})();
