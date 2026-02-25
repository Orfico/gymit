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
