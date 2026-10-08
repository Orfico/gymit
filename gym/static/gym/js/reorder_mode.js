/**
 * GymIt — Modalità "Riordina" per le liste con drag & drop.
 *
 * Il trascinamento non è attivo di default: l'utente lo abilita con un
 * pulsante toggle (icona, aria-pressed) e lo disabilita quando ha finito.
 * Così un tap o un trascinamento accidentale non riordina nulla.
 *
 * Con la modalità attiva il contenitore riceve la classe `reorder-mode`
 * (che rende visibili le maniglie) e gli elementi `itemSelector` diventano
 * draggable; da spenta tornano normali.
 *
 * Ritorna { isActive(), set(bool) } così dragdrop.js / plan_tree.js possono
 * ignorare qualunque gesto che arrivi a modalità spenta.
 */
function initReorderMode({ container, button, itemSelector }) {
    const list = typeof container === 'string' ? document.getElementById(container) : container;
    const toggle = typeof button === 'string' ? document.getElementById(button) : button;
    if (!list || !toggle) return { isActive: () => false, set: () => {} };

    let active = false;

    function set(on) {
        active = !!on;
        list.classList.toggle('reorder-mode', active);
        toggle.setAttribute('aria-pressed', String(active));
        toggle.classList.toggle('btn-warning', active);
        toggle.classList.toggle('btn-outline-secondary', !active);
        list.querySelectorAll(itemSelector).forEach(item => {
            if (active) item.setAttribute('draggable', 'true');
            else item.removeAttribute('draggable');
        });
    }

    toggle.addEventListener('click', () => set(!active));

    // In modalità riordino un tap sulle schede non deve aprirle.
    list.addEventListener('click', (e) => {
        if (!active) return;
        const link = e.target.closest('a');
        if (link && list.contains(link) && !e.target.closest('.dropdown')) e.preventDefault();
    });

    set(false);
    return { isActive: () => active, set };
}
