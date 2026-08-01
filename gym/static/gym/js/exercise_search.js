/**
 * GymIt — Ricerca esercizi (sezione Esercizi)
 *
 * Filtra dal vivo la lista già renderizzata nella pagina (nessuna chiamata
 * di rete: gli esercizi ci sono già tutti nel DOM) e mostra un dropdown di
 * suggerimenti man mano che l'utente digita, con lo stesso stile visivo
 * dell'autocomplete già usato altrove nell'app. Se l'utente non seleziona
 * un suggerimento, la lista resta comunque filtrata su tutti gli esercizi
 * che contengono il testo cercato nel nome.
 */
function initExerciseSearch({ inputId, dropdownId }) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    const emptyState = document.getElementById('exerciseSearchEmpty');
    if (!input || !dropdown) return;

    dropdown.style.cssText = `
        position: absolute; z-index: 1050; width: 100%;
        background: #1a1a1a; border: 1px solid #444;
        border-radius: 10px; margin-top: 4px;
        max-height: 260px; overflow-y: auto;
        display: none; box-shadow: 0 8px 24px rgba(0,0,0,0.5);
    `;

    const items = Array.from(document.querySelectorAll('.exercise-group .swipe-item[data-exercise-name]')).map(el => ({
        el,
        name: el.dataset.exerciseName,
    }));

    let currentMatches = [];
    let highlightedIndex = -1;

    function highlight(text, query) {
        if (!query) return text;
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return text.replace(regex, '<mark class="bg-warning text-dark px-0">$1</mark>');
    }

    // ── Filtro live della lista — applicato ad ogni digitazione, a
    // prescindere dal fatto che l'utente scelga un suggerimento. ──
    function applyFilter(query) {
        const q = query.trim().toLowerCase();
        let anyVisible = false;

        document.querySelectorAll('.exercise-group').forEach(group => {
            let groupHasVisible = false;
            group.querySelectorAll('.swipe-item[data-exercise-name]').forEach(item => {
                const match = !q || item.dataset.exerciseName.toLowerCase().includes(q);
                item.style.display = match ? '' : 'none';
                if (match) groupHasVisible = true;
            });
            group.style.display = groupHasVisible ? '' : 'none';
            if (groupHasVisible) anyVisible = true;
        });

        if (emptyState) emptyState.style.display = (!anyVisible && q) ? 'block' : 'none';
    }

    // ── Dropdown suggerimenti ────────────────────────────────────────
    function showDropdown(query) {
        const q = query.trim().toLowerCase();
        currentMatches = items.filter(i => i.name.toLowerCase().includes(q)).slice(0, 8);
        highlightedIndex = -1;
        dropdown.innerHTML = '';

        if (!currentMatches.length) {
            hideDropdown();
            return;
        }

        currentMatches.forEach((match, idx) => {
            const li = document.createElement('li');
            li.className = 'autocomplete-item px-3 py-2';
            li.style.cursor = 'pointer';
            li.innerHTML = `<span class="fw-semibold text-light">${highlight(match.name, query.trim())}</span>`;
            li.addEventListener('mousedown', (e) => {
                e.preventDefault(); // evita blur prima del click
                selectMatch(match);
            });
            li.addEventListener('mouseover', () => setHighlight(idx));
            dropdown.appendChild(li);
        });

        dropdown.style.display = 'block';
    }

    function hideDropdown() {
        dropdown.style.display = 'none';
        highlightedIndex = -1;
    }

    function setHighlight(idx) {
        const listItems = dropdown.querySelectorAll('.autocomplete-item');
        listItems.forEach((el, i) => {
            el.style.background = i === idx ? '#2a2a2a' : '';
        });
        highlightedIndex = idx;
    }

    function selectMatch(match) {
        input.value = match.name;
        hideDropdown();
        applyFilter(match.name); // nome univoco → mostra solo quell'esercizio
    }

    // ── Event listeners ───────────────────────────────────────────
    input.addEventListener('input', () => {
        const val = input.value;
        applyFilter(val);
        if (val.trim().length >= 2) {
            showDropdown(val);
        } else {
            hideDropdown();
        }
    });

    input.addEventListener('keydown', (e) => {
        const listItems = dropdown.querySelectorAll('.autocomplete-item');
        if (!listItems.length) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setHighlight(Math.min(highlightedIndex + 1, listItems.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setHighlight(Math.max(highlightedIndex - 1, 0));
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (highlightedIndex >= 0 && currentMatches[highlightedIndex]) {
                selectMatch(currentMatches[highlightedIndex]);
            } else {
                hideDropdown();
            }
        } else if (e.key === 'Escape') {
            hideDropdown();
        }
    });

    input.addEventListener('blur', () => {
        setTimeout(hideDropdown, 150);
    });

    input.addEventListener('focus', () => {
        if (input.value.trim().length >= 2) {
            showDropdown(input.value);
        }
    });
}
