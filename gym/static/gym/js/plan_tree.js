/**
 * GymIt — Cartelle e riordino schede (pagina "Le mie schede")
 *
 * Struttura ad albero a un livello: la radice (#plan-tree) contiene
 * cartelle (.plan-folder) e schede sciolte (.drag-item[data-type="plan"])
 * interleaved; ogni cartella contiene solo schede nel suo
 * .plan-folder-body. Le schede si possono trascinare per riordinarle o
 * per spostarle dentro/fuori una cartella; le cartelle si riordinano solo
 * tra loro/le schede sciolte a livello radice (mai annidabili).
 *
 * Al rilascio si risincronizza per intero (non un diff incrementale): un
 * POST alla lista radice + un POST per ogni cartella attualmente
 * renderizzata con il suo elenco corrente di schede. Semplice e robusto:
 * a questa scala (poche schede/cartelle per utente) il costo è trascurabile.
 *
 * Desktop: HTML5 Drag and Drop API. Mobile: Touch Events sul drag-handle.
 */
function initPlanTree({ treeId, reorderRootUrl, csrfToken }) {
    const tree = document.getElementById(treeId);
    if (!tree) return;

    // ── Indicatore di salvataggio (stesso stile di dragdrop.js) ──────
    const savingIndicator = document.createElement('div');
    savingIndicator.className = 'saving-indicator mb-2';
    savingIndicator.innerHTML = `
        <span class="spinner-border spinner-border-sm text-warning" role="status" aria-hidden="true"></span>
        <span>Salvataggio ordine...</span>
    `;
    tree.insertAdjacentElement('beforebegin', savingIndicator);

    // ── Stato condiviso ───────────────────────────────────────────
    let dragged = null;          // .plan-folder o .drag-item[type=plan] trascinato
    let draggedType = null;      // 'plan' | 'folder'
    let placeholder = null;      // segnaposto visivo per il riordino
    let touchOffsetY = 0;
    let touchClone = null;
    let dropFolderTarget = null; // cartella attualmente evidenziata come drop-target

    const ITEM_SELECTOR = '.plan-folder, .drag-item[data-type="plan"]';

    // ── Helpers di struttura ─────────────────────────────────────
    function getSiblingItems(container) {
        return Array.from(container.children).filter(el => el.matches(ITEM_SELECTOR));
    }

    function createPlaceholder(referenceEl) {
        const ph = document.createElement('div');
        ph.className = 'tree-drag-placeholder';
        ph.style.cssText = `height: ${referenceEl.offsetHeight}px;`;
        return ph;
    }

    function setDraggingStyle(el, active) {
        el.style.opacity = active ? '0.4' : '';
    }

    function clearFolderHighlight() {
        if (dropFolderTarget) {
            dropFolderTarget.classList.remove('drag-over');
            dropFolderTarget = null;
        }
    }

    function setFolderHighlight(folderEl) {
        if (dropFolderTarget === folderEl) return;
        clearFolderHighlight();
        dropFolderTarget = folderEl;
        dropFolderTarget.classList.add('drag-over');
    }

    // ── Cosa c'è sotto un punto (mouse o touch) ──────────────────
    function resolveDropTarget(x, y) {
        const el = document.elementFromPoint(x, y);
        if (!el) return null;

        // Solo le schede possono entrare dentro una cartella.
        if (draggedType === 'plan') {
            const folderHeader = el.closest('.plan-folder-header');
            if (folderHeader) {
                const folderEl = folderHeader.closest('.plan-folder');
                if (folderEl && folderEl !== dragged) {
                    return { kind: 'folder', folderEl };
                }
            }
        }

        const siblingItem = el.closest(ITEM_SELECTOR);
        if (siblingItem && siblingItem !== dragged && !dragged.contains(siblingItem)) {
            return { kind: 'sibling', el: siblingItem };
        }

        if (draggedType === 'plan') {
            const folderBody = el.closest('.plan-folder-body');
            if (folderBody) return { kind: 'container', container: folderBody };
        }

        if (el.closest('#' + treeId)) {
            return { kind: 'container', container: tree };
        }
        return null;
    }

    function handleHover(x, y) {
        const target = resolveDropTarget(x, y);
        if (!target) return;

        if (target.kind === 'folder') {
            setFolderHighlight(target.folderEl);
            if (placeholder && placeholder.parentNode) placeholder.remove();
            return;
        }

        clearFolderHighlight();

        if (target.kind === 'sibling') {
            const rect = target.el.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;
            if (y < midY) {
                target.el.parentNode.insertBefore(placeholder, target.el);
            } else {
                target.el.parentNode.insertBefore(placeholder, target.el.nextSibling);
            }
        } else if (target.kind === 'container') {
            if (placeholder.parentNode !== target.container) {
                target.container.appendChild(placeholder);
            }
        }
    }

    function dropIntoFolder(folderEl) {
        const body = folderEl.querySelector('.plan-folder-body');
        const emptyHint = body.querySelector('.plan-folder-empty-hint');
        if (emptyHint) emptyHint.remove();
        body.appendChild(dragged);

        // Espande la cartella per mostrare dove è finita la scheda.
        const collapseEl = folderEl.querySelector('.collapse');
        if (collapseEl && window.bootstrap) {
            window.bootstrap.Collapse.getOrCreateInstance(collapseEl, { toggle: false }).show();
        }
    }

    function endDrag() {
        setDraggingStyle(dragged, false);
        if (touchClone) {
            touchClone.remove();
            touchClone = null;
        }

        if (dropFolderTarget) {
            dropIntoFolder(dropFolderTarget);
        } else if (placeholder && placeholder.parentNode) {
            placeholder.parentNode.insertBefore(dragged, placeholder);
        }
        if (placeholder && placeholder.parentNode) placeholder.remove();

        clearFolderHighlight();
        placeholder = null;
        dragged = null;
        draggedType = null;

        persist();
    }

    // ── Salvataggio — risincronizza per intero ───────────────────
    async function persist() {
        savingIndicator.classList.add('active');
        try {
            const rootOrder = getSiblingItems(tree).map(el => ({
                type: el.dataset.type,
                id: parseInt(el.dataset.id, 10),
            }));
            await fetch(reorderRootUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                body: JSON.stringify({ order: rootOrder }),
            });

            const folderBodies = tree.querySelectorAll('.plan-folder-body');
            for (const body of folderBodies) {
                const ids = getSiblingItems(body).map(el => parseInt(el.dataset.id, 10));
                await fetch(body.dataset.reorderUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
                    body: JSON.stringify({ order: ids }),
                });
            }
        } catch (e) {
            console.error('Reorder error', e);
        } finally {
            savingIndicator.classList.remove('active');
        }
    }

    // ── Desktop: HTML5 Drag and Drop ─────────────────────────────
    tree.addEventListener('dragstart', (e) => {
        const item = e.target.closest(ITEM_SELECTOR);
        if (!item) return;
        dragged = item;
        draggedType = item.dataset.type;
        placeholder = createPlaceholder(item);
        setTimeout(() => setDraggingStyle(item, true), 0);
        e.dataTransfer.effectAllowed = 'move';
    });

    tree.addEventListener('dragover', (e) => {
        if (!dragged) return;
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        handleHover(e.clientX, e.clientY);
    });

    tree.addEventListener('dragend', () => {
        if (!dragged) return;
        endDrag();
    });

    tree.addEventListener('dragenter', (e) => e.preventDefault());

    // ── Mobile: Touch Events (solo dal drag-handle) ──────────────
    tree.addEventListener('touchstart', (e) => {
        const handle = e.target.closest('.drag-handle');
        if (!handle) return;
        const item = handle.closest(ITEM_SELECTOR);
        if (!item) return;

        dragged = item;
        draggedType = item.dataset.type;

        const touch = e.touches[0];
        const rect = item.getBoundingClientRect();
        touchOffsetY = touch.clientY - rect.top;

        placeholder = createPlaceholder(item);

        touchClone = item.cloneNode(true);
        touchClone.style.cssText = `
            position: fixed; left: ${rect.left}px; top: ${rect.top}px;
            width: ${rect.width}px; z-index: 9999; opacity: 0.9;
            pointer-events: none; box-shadow: 0 8px 32px rgba(0,0,0,0.6);
            transform: scale(1.02);
        `;
        document.body.appendChild(touchClone);

        setDraggingStyle(item, true);
        item.parentNode.insertBefore(placeholder, item);

        e.preventDefault();
    }, { passive: false });

    tree.addEventListener('touchmove', (e) => {
        if (!dragged || !touchClone) return;
        e.preventDefault();
        const touch = e.touches[0];
        touchClone.style.top = `${touch.clientY - touchOffsetY}px`;
        handleHover(touch.clientX, touch.clientY);
    }, { passive: false });

    tree.addEventListener('touchend', () => {
        if (!dragged) return;
        endDrag();
    });
}
