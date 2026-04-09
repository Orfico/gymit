/**
 * GymIt — Swipe to delete
 * Swipe a sinistra sull'item rivela il tasto Elimina.
 * Compatibile desktop (mouse) e mobile (touch).
 */

function initSwipeToDelete({ listSelector, onDelete }) {
    const THRESHOLD = 80; // px minimi per considerare uno swipe

    function attachSwipe(item) {
        let startX = 0;
        let currentX = 0;
        let isSwiping = false;
        const inner = item.querySelector('.swipe-inner');
        const deleteBtn = item.querySelector('.swipe-delete-btn');
        if (!inner) return;

        function onStart(x) {
            startX = x;
            currentX = 0;
            isSwiping = true;
            inner.style.transition = 'none';
        }

        function onMove(x) {
            if (!isSwiping) return;
            currentX = x - startX;
            // Solo swipe a sinistra
            if (currentX > 0) currentX = 0;
            const clamped = Math.max(currentX, -120);
            inner.style.transform = `translateX(${clamped}px)`;
        }

        function onEnd() {
            if (!isSwiping) return;
            isSwiping = false;
            inner.style.transition = 'transform 0.2s ease';
            if (currentX < -THRESHOLD) {
                // Apri — mostra il bottone delete
                inner.style.transform = 'translateX(-80px)';
                item.classList.add('swiped-open');
            } else {
                // Chiudi
                inner.style.transform = 'translateX(0)';
                item.classList.remove('swiped-open');
            }
        }

        // Touch
        inner.addEventListener('touchstart', (e) => onStart(e.touches[0].clientX), { passive: true });
        inner.addEventListener('touchmove', (e) => onMove(e.touches[0].clientX), { passive: true });
        inner.addEventListener('touchend', onEnd);

        // Mouse (desktop)
        inner.addEventListener('mousedown', (e) => onStart(e.clientX));
        document.addEventListener('mousemove', (e) => { if (isSwiping) onMove(e.clientX); });
        document.addEventListener('mouseup', () => { if (isSwiping) onEnd(); });

        // Click sul bottone delete
        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => {
                if (confirm('Rimuovere dalla scheda?')) {
                    onDelete(item);
                }
                // Reset swipe se annullato
                inner.style.transform = 'translateX(0)';
                item.classList.remove('swiped-open');
            });
        }

        // Tap sull'inner chiude lo swipe se era aperto
        inner.addEventListener('click', (e) => {
            if (item.classList.contains('swiped-open')) {
                e.preventDefault();
                e.stopPropagation();
                inner.style.transition = 'transform 0.2s ease';
                inner.style.transform = 'translateX(0)';
                item.classList.remove('swiped-open');
            }
        });
    }

    document.querySelectorAll(listSelector).forEach(attachSwipe);
}