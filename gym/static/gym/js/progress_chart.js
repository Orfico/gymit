/**
 * GymIt — Progress Chart
 * Inizializza il grafico Chart.js per l'andamento del 1RM di un esercizio.
 */

function initProgressChart(canvasId, data) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !data.length) return;

    const labels = data.map(d => d.date);
    const oneRmValues = data.map(d => parseFloat(d.one_rm));
    const weightValues = data.map(d => parseFloat(d.weight));

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '1RM Teorico (kg)',
                    data: oneRmValues,
                    borderColor: '#ffc107',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#ffc107',
                    pointRadius: 5,
                    pointHoverRadius: 8,
                    borderWidth: 2,
                },
                {
                    label: 'Carico effettivo (kg)',
                    data: weightValues,
                    borderColor: '#6c757d',
                    backgroundColor: 'transparent',
                    fill: false,
                    tension: 0.4,
                    pointBackgroundColor: '#6c757d',
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                }
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    labels: {
                        color: '#aaa',
                        font: { size: 12 },
                    }
                },
                tooltip: {
                    backgroundColor: '#1a1a1a',
                    borderColor: '#333',
                    borderWidth: 1,
                    titleColor: '#fff',
                    bodyColor: '#ccc',
                    callbacks: {
                        afterBody: function(items) {
                            const idx = items[0].dataIndex;
                            const d = data[idx];
                            return [`Eseguito: ${d.sets} serie × ${d.reps} reps`];
                        }
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#666', maxTicksLimit: 8 },
                    grid: { color: '#1e1e1e' }
                },
                y: {
                    ticks: {
                        color: '#666',
                        callback: v => v + ' kg'
                    },
                    grid: { color: '#1e1e1e' }
                }
            }
        }
    });
}
