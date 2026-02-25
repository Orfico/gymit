/**
 * GymIt — Drag & Drop reorder per la lista esercizi in scheda.
 *
 * Desktop : HTML5 Drag and Drop API (draggable="true")
 * Mobile  : Touch Events (touchstart / touchmove / touchend)
 *
 * Al rilascio salva il nuovo ordine via fetch POST → /plans/<pk>/reorder/
 */

function initDragDrop({ listId, reorderUrl, csrfToken }) {
    const list = document.getElementById(listId);
    if (!list) return;

    // ── Stato condiviso ───────────────────────────────────────────
    let dragged = null;         // elemento che si sta trascinando
    let placeholder = null;     // segnaposto visivo durante il drag
    let touchOffsetY = 0;       // offset touch rispetto all'elemento

    // ── Helpers ───────────────────────────────────────────────────

    function getItems() {
        return [...list.querySelectorAll('.drag-item')];
    }

    function createPlaceholder(referenceEl) {
        const ph = document.createElement('div');
        ph.id = 'drag-placeholder';
        ph.style.cssText = `
            height: ${referenceEl.offsetHeight}px;
            border: 2px dashed #ffc107;
            border-radius: 12px;
            background: rgba(255,193,7,0.05);
            margin-bottom: 8px;
            transition: none;
        `;
        return ph;
    }

    function getItemAtY(y) {
        // Trova l'item sotto il punto Y (usato dai touch events)
        return getItems().find(item => {
            if (item === dragged) return false;
            const rect = item.getBoundingClientRect();
            return y >= rect.top && y <= rect.bottom;
        });
    }

    function insertPlaceholderBefore(target) {
        if (placeholder && placeholder.nextSibling === target) return;
        list.insertBefore(placeholder, target);
    }

    function insertPlaceholderAfter(target) {
        if (placeholder && target.nextSibling === placeholder) return;
        target.insertAdjacentElement('afterend', placeholder);
    }

    async function saveOrder() {
        const ids = getItems().map(el => parseInt(el.dataset.id));
        try {
            const res = await fetch(reorderUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({ order: ids }),
            });
            if (!res.ok) console.error('Reorder failed', await res.text());
        } catch (e) {
            console.error('Reorder error', e);
        }
    }

    function setDraggingStyle(el, active) {
        if (active) {
            el.style.opacity = '0.4';
            el.style.transform = 'scale(0.98)';
        } else {
            el.style.opacity = '';
            el.style.transform = '';
        }
    }

    // ── Desktop: HTML5 Drag and Drop ──────────────────────────────

    list.addEventListener('dragstart', (e) => {
        dragged = e.target.closest('.drag-item');
        if (!dragged) return;
        placeholder = createPlaceholder(dragged);
        // Piccolo delay per permettere al browser di catturare lo snapshot
        setTimeout(() => setDraggingStyle(dragged, true), 0);
        e.dataTransfer.effectAllowed = 'move';
    });

    list.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        const target = e.target.closest('.drag-item');
        if (!target || target === dragged) return;

        const rect = target.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        if (e.clientY < midY) {
            insertPlaceholderBefore(target);
        } else {
            insertPlaceholderAfter(target);
        }
    });

    list.addEventListener('dragend', () => {
        if (!dragged) return;
        setDraggingStyle(dragged, false);
        if (placeholder && placeholder.parentNode) {
            placeholder.parentNode.insertBefore(dragged, placeholder);
            placeholder.remove();
        }
        placeholder = null;
        dragged = null;
        saveOrder();
    });

    // Evita il flash del "proibito" quando si entra nel placeholder
    list.addEventListener('dragenter', (e) => e.preventDefault());

    // ── Mobile: Touch Events ──────────────────────────────────────

    let touchClone = null;  // copia visiva dell'elemento che segue il dito

    list.addEventListener('touchstart', (e) => {
        const handle = e.target.closest('.drag-handle');
        if (!handle) return;

        dragged = handle.closest('.drag-item');
        if (!dragged) return;

        const touch = e.touches[0];
        const rect = dragged.getBoundingClientRect();
        touchOffsetY = touch.clientY - rect.top;

        placeholder = createPlaceholder(dragged);

        // Crea una copia visiva che segue il dito
        touchClone = dragged.cloneNode(true);
        touchClone.style.cssText = `
            position: fixed;
            left: ${rect.left}px;
            top: ${rect.top}px;
            width: ${rect.width}px;
            z-index: 9999;
            opacity: 0.9;
            pointer-events: none;
            box-shadow: 0 8px 32px rgba(0,0,0,0.6);
            transform: scale(1.02);
            transition: none;
        `;
        document.body.appendChild(touchClone);

        setDraggingStyle(dragged, true);
        list.insertBefore(placeholder, dragged);

        e.preventDefault(); // evita scroll durante il drag
    }, { passive: false });

    list.addEventListener('touchmove', (e) => {
        if (!dragged || !touchClone) return;
        e.preventDefault();

        const touch = e.touches[0];

        // Sposta la copia visiva
        touchClone.style.top = `${touch.clientY - touchOffsetY}px`;

        // Trova l'elemento sotto la posizione corrente del dito
        const target = getItemAtY(touch.clientY);
        if (!target) return;

        const rect = target.getBoundingClientRect();
        const midY = rect.top + rect.height / 2;
        if (touch.clientY < midY) {
            insertPlaceholderBefore(target);
        } else {
            insertPlaceholderAfter(target);
        }
    }, { passive: false });

    list.addEventListener('touchend', () => {
        if (!dragged) return;

        setDraggingStyle(dragged, false);
        if (placeholder && placeholder.parentNode) {
            placeholder.parentNode.insertBefore(dragged, placeholder);
            placeholder.remove();
        }
        if (touchClone) {
            touchClone.remove();
            touchClone = null;
        }
        placeholder = null;
        dragged = null;
        saveOrder();
    });

    // ── Abilita draggable su tutti gli item ───────────────────────

    getItems().forEach(item => {
        item.setAttribute('draggable', 'true');
    });
}
