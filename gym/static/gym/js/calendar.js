/**
 * GymIt — Calendario allenamenti
 *
 * Toccando una cella carica via fetch il dettaglio della giornata e lo
 * mostra in un modale: schede allenate quel giorno, con link alla scheda
 * (se esiste ancora) e possibilità di eliminare la registrazione.
 */
function initWorkoutCalendar({ modalId, titleId, bodyId, csrfToken }) {
    var modalEl = document.getElementById(modalId);
    var titleEl = document.getElementById(titleId);
    var bodyEl = document.getElementById(bodyId);
    if (!modalEl) return;

    var modal = new bootstrap.Modal(modalEl);

    function escapeHtml(str) {
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

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
        html += '</ul>';
        return html;
    }

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
                bodyEl.innerHTML = data.sessions.length
                    ? renderSessions(data.sessions)
                    : renderEmpty();

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

    document.querySelectorAll('.calendar-cell[data-url]').forEach(function (cell) {
        cell.addEventListener('click', function () {
            titleEl.textContent = 'Giornata';
            modal.show();
            loadDay(cell.dataset.url);
        });
    });
}
