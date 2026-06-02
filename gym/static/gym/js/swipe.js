/**
 * GymIt — Swipe to delete
 * Swipe a sinistra rivela il tasto Elimina.
 */

function initSwipeToDelete({ listSelector, onDelete, confirmMessage = 'Eliminare?' }) {
    const THRESHOLD = 60;

    document.querySelectorAll(listSelector).forEach(item => {
        const inner = item.querySelector('.swipe-inner');
        const deleteBtn = item.querySelector('.swipe-delete-btn');
        if (!inner) return;

        let startX = 0, startY = 0, currentX = 0, tracking = false, didSwipe = false;

        function reset() {
            inner.style.transition = 'transform 0.2s ease';
            inner.style.transform = 'translateX(0)';
            item.classList.remove('swiped-open');
        }

        function open() {
            inner.style.transition = 'transform 0.2s ease';
            inner.style.transform = 'translateX(-80px)';
            item.classList.add('swiped-open');
        }

        inner.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            currentX = 0;
            tracking = true;
            didSwipe = false;
            inner.style.transition = 'none';
        }, { passive: true });

        inner.addEventListener('touchmove', (e) => {
            if (!tracking) return;
            const dx = e.touches[0].clientX - startX;
            const dy = e.touches[0].clientY - startY;

            // Se il movimento è prevalentemente verticale, non intercettare
            if (!didSwipe && Math.abs(dy) > Math.abs(dx)) {
                tracking = false;
                inner.style.transform = 'translateX(0)';
                return;
            }

            didSwipe = true;
            currentX = Math.min(0, Math.max(dx, -120));
            inner.style.transform = `translateX(${currentX}px)`;
        }, { passive: true });

        inner.addEventListener('touchend', () => {
            if (!tracking) return;
            tracking = false;
            if (currentX < -THRESHOLD) {
                open();
            } else {
                reset();
            }
        });

        // Chiudi se si tocca altrove
        document.addEventListener('touchstart', (e) => {
            if (item.classList.contains('swiped-open') && !item.contains(e.target)) {
                reset();
            }
        }, { passive: true });

        if (deleteBtn) {
            deleteBtn.addEventListener('click', () => {
                if (confirm(confirmMessage)) {
                    onDelete(item);
                } else {
                    reset();
                }
            });
        }
    });
}