/**
 * GymIt — Exercise Autocomplete
 *
 * Uso: chiamare initExerciseAutocomplete(config) dopo il DOM ready.
 * Sostituisce visivamente il <select> nativo con un campo testuale +
 * dropdown, mantenendo il select originale hidden per la submission
 * del form Django (la validazione lato server rimane invariata).
 */

function initExerciseAutocomplete({ selectId, endpointUrl }) {
    const select = document.getElementById(selectId);
    if (!select) return;

    // ── Costruzione DOM ───────────────────────────────────────────
    const wrapper = document.createElement('div');
    wrapper.className = 'autocomplete-wrapper position-relative';

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'form-control';
    input.placeholder = 'Cerca esercizio...';
    input.autocomplete = 'off';
    input.setAttribute('aria-label', 'Cerca esercizio');

    const dropdown = document.createElement('ul');
    dropdown.className = 'autocomplete-dropdown list-unstyled mb-0';
    dropdown.style.cssText = `
        position: absolute; z-index: 1050; width: 100%;
        background: #1a1a1a; border: 1px solid #444;
        border-radius: 10px; margin-top: 4px;
        max-height: 260px; overflow-y: auto;
        display: none; box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    `;

    // Nascondi il select originale — Django lo usa per la submission
    select.style.display = 'none';
    select.insertAdjacentElement('afterend', wrapper);
    wrapper.appendChild(input);
    wrapper.appendChild(dropdown);

    // Se c'è già un valore preselezionato (es. ?exercise=N), mostralo
    const preselected = select.options[select.selectedIndex];
    if (preselected && preselected.value) {
        input.value = preselected.text;
    }

    // ── Stato interno ─────────────────────────────────────────────
    let debounceTimer = null;
    let currentResults = [];
    let highlightedIndex = -1;

    // ── Helpers ───────────────────────────────────────────────────
    function showDropdown(results) {
        dropdown.innerHTML = '';
        highlightedIndex = -1;

        if (!results.length) {
            const empty = document.createElement('li');
            empty.className = 'px-3 py-2 text-secondary small';
            empty.textContent = 'Nessun risultato';
            dropdown.appendChild(empty);
        } else {
            results.forEach((ex, idx) => {
                const li = document.createElement('li');
                li.className = 'autocomplete-item px-3 py-2';
                li.style.cursor = 'pointer';
                li.innerHTML = `
                    <span class="fw-semibold text-light">${highlight(ex.name, input.value)}</span>
                    <span class="ms-2 badge bg-secondary small">${ex.muscle_group}</span>
                `;
                li.addEventListener('mousedown', (e) => {
                    e.preventDefault(); // evita blur prima del click
                    selectExercise(ex);
                });
                li.addEventListener('mouseover', () => setHighlight(idx));
                dropdown.appendChild(li);
            });
        }

        currentResults = results;
        dropdown.style.display = 'block';
    }

    function hideDropdown() {
        dropdown.style.display = 'none';
        highlightedIndex = -1;
    }

    function selectExercise(ex) {
        input.value = ex.name;
        select.value = ex.id;
        hideDropdown();
    }

    function setHighlight(idx) {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        items.forEach((el, i) => {
            el.style.background = i === idx ? '#2a2a2a' : '';
        });
        highlightedIndex = idx;
    }

    function highlight(text, query) {
        if (!query) return text;
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<mark class="bg-warning text-dark px-0">$1</mark>');
    }

    async function search(query) {
        try {
            const res = await fetch(`${endpointUrl}?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            showDropdown(data.results);
        } catch {
            hideDropdown();
        }
    }

    // ── Event listeners ───────────────────────────────────────────
    input.addEventListener('input', () => {
        const val = input.value.trim();

        // Reset selezione se l'utente modifica il testo
        select.value = '';

        if (val.length < 2) {
            hideDropdown();
            return;
        }

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => search(val), 200);
    });

    input.addEventListener('keydown', (e) => {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        if (!items.length) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setHighlight(Math.min(highlightedIndex + 1, items.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setHighlight(Math.max(highlightedIndex - 1, 0));
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (highlightedIndex >= 0 && currentResults[highlightedIndex]) {
                selectExercise(currentResults[highlightedIndex]);
            }
        } else if (e.key === 'Escape') {
            hideDropdown();
        }
    });

    input.addEventListener('blur', () => {
        // Piccolo delay per permettere il click sul dropdown
        setTimeout(hideDropdown, 150);
    });

    input.addEventListener('focus', () => {
        if (input.value.trim().length >= 2) {
            search(input.value.trim());
        }
    });
}
