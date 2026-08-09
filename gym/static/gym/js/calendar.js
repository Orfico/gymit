/**
 * GymIt — Calendario allenamenti
 *
 * Toccando una cella carica via fetch il dettaglio della giornata e lo
 * mostra in un modale: schede allenate quel giorno, con link alla scheda
 * (se esiste ancora) e possibilità di eliminare la registrazione.
 *
 * Se la giornata è vuota (e non è nel futuro) compare "Registra
 * allenamento", che apre un selettore con tutte le schede — attive e
 * archiviate — filtrabili per nome. Le schede arrivano già con la pagina:
 * sono poche per utente, quindi il filtro è istantaneo e funziona anche
 * offline, come già fa la ricerca nella sezione esercizi.
 */
function initWorkoutCalendar({ modalId, titleId, bodyId, csrfToken, plans }) {
    var modalEl = document.getElementById(modalId);
    var titleEl = document.getElementById(titleId);
    var bodyEl = document.getElementById(bodyId);
    if (!modalEl) return;

    var modal = new bootstrap.Modal(modalEl);
    var allPlans = plans || [];

    var footerEl = document.getElementById('dayLogFooter');
    var logBtn = document.getElementById('dayLogBtn');
    var pickerEl = document.getElementById('dayLogPicker');
    var searchEl = document.getElementById('dayLogSearch');
    var resultsEl = document.getElementById('dayLogResults');
    var formEl = document.getElementById('dayLogForm');
    var planIdEl = document.getElementById('dayLogPlanId');
    var dateEl = document.getElementById('dayLogDate');

    var currentDate = null;
    var highlightedIndex = -1;
    var currentMatches = [];

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function highlightMatch(text, query) {
        var safe = escapeHtml(text);
        if (!query) return safe;
        var escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return safe.replace(
            new RegExp('(' + escaped + ')', 'gi'),
            '<mark class="bg-warning text-dark px-0">$1</mark>'
        );
    }

    // ── Dettaglio giornata ───────────────────────────────────────────
    function renderEmpty() {
        return '<p class="text-secondary text-center small mb-0 py-2">' +
               'Nessun allenamento registrato in questa giornata.</p>';
    }

    function renderSessions(sessions) {
        var html = '<ul class="list-unstyled mb-0">';
        sessions.forEach(function (s) {
            var name = escapeHtml(s.plan_name);
            // La scheda può essere stata eliminata (o non essere mai esistita,
            // se importata da CSV): in quel caso niente link, solo il nome.
            var label = s.plan_url
                ? '<a href="' + s.plan_url + '" class="text-warning text-decoration-none fw-semibold">' +
                  name + '</a>'
                : '<span class="fw-semibold">' + name + '</span>';

            html += '<li class="d-flex align-items-center gap-2 py-2 border-bottom border-secondary">' +
                    '<i class="bi bi-lightning-charge-fill text-warning"></i>' +
                    '<span class="flex-grow-1 min-w-0 text-truncate">' + label + '</span>' +
                    '<form method="post" action="' + s.delete_url + '" class="m-0 session-delete-form">' +
                    '<input type="hidden" name="csrfmiddlewaretoken" value="' + csrfToken + '">' +
                    '<button type="submit" class="btn btn-outline-danger btn-sm" ' +
                    'aria-label="Elimina ' + name + '"><i class="bi bi-trash"></i></button>' +
                    '</form>' +
                    '</li>';
        });
        return html + '</ul>';
    }

    // ── Selettore schede ─────────────────────────────────────────────
    function renderResults(query) {
        var q = query.trim().toLowerCase();
        currentMatches = allPlans.filter(function (p) {
            return !q || p.name.toLowerCase().indexOf(q) !== -1;
        });
        highlightedIndex = -1;

        if (!allPlans.length) {
            resultsEl.innerHTML =
                '<li class="text-secondary small text-center py-3">' +
                'Non hai ancora nessuna scheda.</li>';
            return;
        }
        if (!currentMatches.length) {
            resultsEl.innerHTML =
                '<li class="text-secondary small text-center py-3">' +
                'Nessuna scheda trovata.</li>';
            return;
        }

        resultsEl.innerHTML = currentMatches.map(function (p, i) {
            // Le archiviate restano selezionabili ma dichiarate come tali.
            var badge = p.is_active
                ? ''
                : '<span class="badge bg-secondary fw-normal ms-2" style="font-size:10px;">' +
                  'Archiviata</span>';
            return '<li><button type="button" class="day-log-option" data-index="' + i + '">' +
                   '<i class="bi bi-journal-text text-warning me-2"></i>' +
                   '<span class="flex-grow-1 min-w-0 text-truncate">' +
                   highlightMatch(p.name, q) + '</span>' + badge +
                   '</button></li>';
        }).join('');
    }

    function setHighlight(index) {
        var options = resultsEl.querySelectorAll('.day-log-option');
        options.forEach(function (o) { o.classList.remove('active'); });
        if (index >= 0 && index < options.length) {
            options[index].classList.add('active');
            options[index].scrollIntoView({ block: 'nearest' });
        }
        highlightedIndex = index;
    }

    function submitPlan(plan) {
        if (!plan || !currentDate) return;
        planIdEl.value = plan.id;
        dateEl.value = currentDate;
        showPageLoader('Registrazione...');
        formEl.submit();
    }

    function openPicker() {
        logBtn.hidden = true;
        pickerEl.hidden = false;
        searchEl.value = '';
        renderResults('');
        searchEl.focus();
    }

    function resetFooter() {
        footerEl.hidden = true;
        pickerEl.hidden = true;
        logBtn.hidden = false;
        searchEl.value = '';
        resultsEl.innerHTML = '';
        currentMatches = [];
        highlightedIndex = -1;
    }

    if (logBtn) {
        logBtn.addEventListener('click', openPicker);

        searchEl.addEventListener('input', function () {
            renderResults(searchEl.value);
        });

        searchEl.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setHighlight(Math.min(highlightedIndex + 1, currentMatches.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                setHighlight(Math.max(highlightedIndex - 1, 0));
            } else if (e.key === 'Enter') {
                e.preventDefault();
                // Senza selezione esplicita vale il primo risultato: con una
                // sola scheda filtrata è quasi sempre quella che si voleva.
                var index = highlightedIndex >= 0 ? highlightedIndex : 0;
                submitPlan(currentMatches[index]);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                pickerEl.hidden = true;
                logBtn.hidden = false;
            }
        });

        resultsEl.addEventListener('click', function (e) {
            var option = e.target.closest('.day-log-option');
            if (!option) return;
            submitPlan(currentMatches[parseInt(option.dataset.index, 10)]);
        });
    }

    // ── Caricamento giornata ─────────────────────────────────────────
    function loadDay(url) {
        bodyEl.innerHTML = '<div class="text-center py-3">' +
            '<div class="spinner-border spinner-border-sm text-warning" role="status">' +
            '<span class="visually-hidden">Caricamento...</span></div></div>';

        fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
            .then(function (res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(function (data) {
                titleEl.textContent = data.date_label;
                currentDate = data.date;
                bodyEl.innerHTML = data.sessions.length
                    ? renderSessions(data.sessions)
                    : renderEmpty();

                // Il bottone compare solo su giornate vuote e non future.
                if (footerEl) footerEl.hidden = !(data.sessions.length === 0 && data.can_log);

                bodyEl.querySelectorAll('.session-delete-form').forEach(function (form) {
                    form.addEventListener('submit', function (e) {
                        if (!confirm('Eliminare questa registrazione?')) {
                            e.preventDefault();
                            return;
                        }
                        showPageLoader('Eliminazione in corso...');
                    });
                });
            })
            .catch(function () {
                bodyEl.innerHTML =
                    '<p class="text-danger text-center small mb-0 py-2">' +
                    'Impossibile caricare la giornata.</p>';
            });
    }

    modalEl.addEventListener('hidden.bs.modal', resetFooter);

    document.querySelectorAll('.calendar-cell[data-url]').forEach(function (cell) {
        cell.addEventListener('click', function () {
            titleEl.textContent = 'Giornata';
            resetFooter();
            modal.show();
            loadDay(cell.dataset.url);
        });
    });
}
