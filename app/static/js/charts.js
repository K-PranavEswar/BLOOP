/* ==========================================================
   HemoPulse AI Pro – SaaS UI Chart Configurations
   ========================================================== */

/**
 * Common chart options for the clean SaaS aesthetic.
 */
function getCommonOptions() {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: {
                    color: '#666666', // text-light
                    font: { family: 'Inter, sans-serif' },
                    usePointStyle: true,
                    padding: 16
                }
            },
            tooltip: {
                backgroundColor: '#ffffff',
                titleColor: '#111111',
                bodyColor: '#666666',
                borderColor: '#e8e8e8',
                borderWidth: 1,
                padding: 12,
                boxPadding: 6,
                usePointStyle: true,
                titleFont: { family: 'Inter', weight: 600 },
                bodyFont: { family: 'Inter' }
            }
        },
        scales: {
            y: {
                grid: {
                    color: '#e8e8e8',
                    drawBorder: false
                },
                ticks: {
                    color: '#666666',
                    font: { family: 'Inter' }
                },
                beginAtZero: true
            },
            x: {
                grid: {
                    display: false,
                    drawBorder: false
                },
                ticks: {
                    color: '#666666',
                    font: { family: 'Inter' }
                }
            }
        }
    };
}

/**
 * Create an Inventory Bar Chart
 */
function createInventoryChart(canvasId, labels, data, thresholds) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const colors = data.map((val, i) => {
        if (thresholds && val < thresholds[i]) return 'rgba(239, 68, 68, 1)'; // Danger
        if (thresholds && val < thresholds[i] * 1.5) return 'rgba(245, 158, 11, 1)'; // Warning
        return 'rgba(16, 185, 129, 1)'; // Success
    });

    const options = getCommonOptions();
    options.plugins.legend.display = false;

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Current Stock (Units)',
                data: data,
                backgroundColor: colors.map(c => c.replace('1)', '0.8)')),
                borderColor: colors,
                borderWidth: 1,
                borderRadius: 8,
                barPercentage: 0.6,
                hoverBackgroundColor: colors
            }]
        },
        options: options
    });
}

/**
 * Create a Request Status Doughnut Chart
 */
function createStatusDoughnut(canvasId, statusData) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const options = getCommonOptions();
    options.scales = {}; // Remove scales for doughnut
    options.cutout = '70%';

    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Pending', 'Approved', 'Rejected', 'Completed'],
            datasets: [{
                data: [
                    statusData.pending || 0,
                    statusData.approved || 0,
                    statusData.rejected || 0,
                    statusData.completed || 0
                ],
                backgroundColor: [
                    'rgba(59, 130, 246, 0.8)', // Info
                    'rgba(16, 185, 129, 0.8)', // Success
                    'rgba(239, 68, 68, 0.8)',  // Danger
                    'rgba(139, 92, 246, 0.8)'  // Purple
                ],
                borderColor: '#ffffff',
                borderWidth: 2,
                hoverOffset: 4
            }]
        },
        options: options
    });
}
