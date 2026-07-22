/**
 * GymIt — Pallini serie completate (pagina scheda)
 *
 * Durante l'allenamento l'utente tocca un pallino per segnare una serie
 * come completata (grigio → giallo) e di nuovo per annullarla. Stato
 * persistito in localStorage — sopravvive alla chiusura dell'app — finché
 * non viene azzerato esplicitamente col tasto di reset.
 */
function initSetDots({ planId, resetButtonId }) {
    var STORAGE_KEY = 'gymit_completed_sets_plan_' + planId;

    function loadState() {
        try {
            var raw = localStorage.getItem(STORAGE_KEY);
            return raw ? JSON.parse(raw) : {};
        } catch (e) {
            return {};
        }
    }

    function saveState() {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }

    var state = loadState();

    function renderContainer(container) {
        var peId = container.dataset.plannedExerciseId;
        var targetSets = parseInt(container.dataset.targetSets, 10) || 0;
        var completed = state[peId] || [];

        container.innerHTML = '';
        for (var i = 0; i < targetSets; i++) {
            var dot = document.createElement('button');
            dot.type = 'button';
            dot.className = 'set-dot' + (completed[i] ? ' completed' : '');
            dot.dataset.setIndex = i;
            dot.setAttribute('aria-label', 'Serie ' + (i + 1) + (completed[i] ? ' completata' : ' da completare'));
            container.appendChild(dot);
        }
    }

    function toggleDot(container, index) {
        var peId = container.dataset.plannedExerciseId;
        var targetSets = parseInt(container.dataset.targetSets, 10) || 0;
        if (!state[peId]) state[peId] = new Array(targetSets).fill(false);
        state[peId][index] = !state[peId][index];
        saveState();
        renderContainer(container);
    }

    document.querySelectorAll('.set-dots').forEach(function (container) {
        renderContainer(container);
        container.addEventListener('click', function (e) {
            var dot = e.target.closest('.set-dot');
            if (!dot) return;
            e.preventDefault();
            e.stopPropagation();
            toggleDot(container, parseInt(dot.dataset.setIndex, 10));
        });
    });

    var resetBtn = resetButtonId ? document.getElementById(resetButtonId) : null;
    if (resetBtn) {
        resetBtn.addEventListener('click', function () {
            if (!confirm('Azzerare tutte le serie completate in questa scheda?')) return;
            state = {};
            saveState();
            document.querySelectorAll('.set-dots').forEach(renderContainer);
        });
    }
}
