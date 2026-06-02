/**
 * GymIt — Sparkline mini-chart per la dashboard
 * Legge i dati da un tag <script type="application/json"> e renderizza
 * una linea 1RM minimale su ogni <canvas data-sparkline-src="...">.
 */
function initSparklines() {
    document.querySelectorAll('canvas[data-sparkline-src]').forEach(canvas => {
        const srcId = canvas.dataset.sparklineSrc;
        const dataEl = document.getElementById(srcId);
        if (!dataEl) return;

        const data = JSON.parse(dataEl.textContent);
        if (data.length < 2) return;

        new Chart(canvas, {
            type: 'line',
            data: {
                labels: data.map(d => d.date),
                datasets: [{
                    data: data.map(d => d.one_rm),
                    borderColor: '#ffc107',
                    borderWidth: 2,
                    pointRadius: 0,
                    tension: 0.4,
                    fill: false,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { enabled: false },
                },
                scales: {
                    x: { display: false },
                    y: { display: false },
                },
            },
        });
    });
}
