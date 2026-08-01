/**
 * GymIt — Main JS
 * Preview in tempo reale del massimale teorico nel form di log.
 */

document.addEventListener('DOMContentLoaded', function () {
    const weightInput = document.getElementById('id_weight');
    const repsInput = document.getElementById('id_reps');
    const preview = document.getElementById('oneRmPreview');
    const oneRmValue = document.getElementById('oneRmValue');

    if (!weightInput || !repsInput || !preview) return;

    function epley(weight, reps) {
        if (!weight || !reps || reps < 1) return null;
        if (reps === 1) return weight.toFixed(1);
        return (weight * (1 + reps / 30)).toFixed(1);
    }

    function updatePreview() {
        const weight = parseFloat(weightInput.value);
        const reps = parseInt(repsInput.value);

        if (weight > 0 && reps > 0) {
            const rm = epley(weight, reps);
            if (rm) {
                oneRmValue.textContent = rm;
                preview.style.display = 'block';
            }
        } else {
            preview.style.display = 'none';
        }
    }

    weightInput.addEventListener('input', updatePreview);
    repsInput.addEventListener('input', updatePreview);
    updatePreview();
});

/**
 * GymIt — Loading states
 *
 * Stile coerente per ogni operazione che richiede un'attesa:
 *  - showButtonLoading()  → spinner-border-sm inline sul bottone che ha
 *    scatenato l'azione (submit di form standard).
 *  - showPageLoader()     → overlay a schermo intero con spinner-border
 *    warning, usato per navigazioni innescate da JS (es. swipe-to-delete)
 *    dove non c'è un bottone visibile su cui agire.
 *
 * Entrambi riusano le stesse classi Bootstrap già presenti in
 * plan_import.html, per mantenere lo stile uniforme in tutta l'app.
 */

function showButtonLoading(button, loadingText) {
    if (!button || button.dataset.loading === '1') return;
    button.dataset.loading = '1';
    button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${loadingText || button.dataset.loadingText || 'Attendere...'}`;
}

function resetButtonLoading(button) {
    if (!button || button.dataset.loading !== '1') return;
    button.innerHTML = button.dataset.originalHtml;
    button.disabled = false;
    delete button.dataset.loading;
}

function showPageLoader(message) {
    hidePageLoader();
    const overlay = document.createElement('div');
    overlay.id = 'pageLoaderOverlay';
    overlay.className = 'page-loader-overlay';
    overlay.innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-warning" role="status">
                <span class="visually-hidden">Caricamento...</span>
            </div>
            <p class="text-secondary small mt-3 mb-0">${message || 'Attendere...'}</p>
        </div>
    `;
    document.body.appendChild(overlay);
}

function hidePageLoader() {
    const overlay = document.getElementById('pageLoaderOverlay');
    if (overlay) overlay.remove();
}

document.addEventListener('DOMContentLoaded', function () {
    // Spinner automatico sul bottone submit di tutti i form "standard".
    // I form costruiti dinamicamente via JS (es. swipe-to-delete) non hanno
    // un bottone submit al loro interno e restano quindi esclusi: per quei
    // casi si usa showPageLoader() esplicitamente prima dell'invio.
    document.querySelectorAll('form:not([data-no-loading])').forEach(function (form) {
        form.addEventListener('submit', function () {
            if (form.checkValidity && !form.checkValidity()) return;
            const submitBtn = form.querySelector('button[type="submit"], input[type="submit"]');
            showButtonLoading(submitBtn);
        });
    });
});

// Se l'utente torna indietro con il tasto Indietro del browser, la pagina
// può essere ripristinata dalla bfcache con i bottoni ancora disabilitati:
// li riportiamo allo stato originale.
window.addEventListener('pageshow', function (e) {
    if (!e.persisted) return;
    document.querySelectorAll('[data-loading="1"]').forEach(resetButtonLoading);
    hidePageLoader();
});
