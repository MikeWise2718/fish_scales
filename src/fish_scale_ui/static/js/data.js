/**
 * Fish Scale Measurement UI - Data Tab
 */

window.data = (function() {
    let tubercles = [];
    let edges = [];
    let statistics = {};

    // Update data and render tables
    function setData(newTubercles, newEdges, newStatistics) {
        tubercles = newTubercles || [];
        edges = newEdges || [];
        statistics = newStatistics || {};

        renderTubercleTable();
        renderEdgeTable();
        renderStatistics();
    }

    // Clear data
    function clear() {
        tubercles = [];
        edges = [];
        statistics = {};
        renderTubercleTable();
        renderEdgeTable();
        renderStatistics();
    }

    // Render tubercle table
    function renderTubercleTable() {
        const tbody = document.getElementById('tubTableBody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (tubercles.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="5" class="empty-table">No tubercles detected</td>';
            tbody.appendChild(row);
            return;
        }

        tubercles.forEach(tub => {
            const row = document.createElement('tr');
            row.dataset.tubId = tub.id;
            row.innerHTML = `
                <td>${tub.id}</td>
                <td>${tub.centroid_x.toFixed(1)}</td>
                <td>${tub.centroid_y.toFixed(1)}</td>
                <td>${tub.diameter_um.toFixed(2)}</td>
                <td>${(tub.circularity * 100).toFixed(1)}%</td>
            `;
            row.addEventListener('click', () => {
                highlightTubercleRow(tub.id);
                if (window.overlay) {
                    window.overlay.highlightTubercle(tub.id);
                }
            });
            tbody.appendChild(row);
        });
    }

    // Render edge table
    function renderEdgeTable() {
        const tbody = document.getElementById('itcTableBody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (edges.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="5" class="empty-table">No connections detected</td>';
            tbody.appendChild(row);
            return;
        }

        edges.forEach((edge, idx) => {
            const row = document.createElement('tr');
            row.dataset.edgeIdx = idx;
            row.innerHTML = `
                <td>${edge.id1}</td>
                <td>${edge.id2}</td>
                <td>${edge.center_distance_um.toFixed(2)}</td>
                <td>${edge.edge_distance_um.toFixed(2)}</td>
            `;
            row.addEventListener('click', () => {
                highlightEdgeRow(idx);
                if (window.overlay) {
                    window.overlay.highlightEdge(idx);
                }
            });
            tbody.appendChild(row);
        });
    }

    // Render statistics panel
    function renderStatistics() {
        const panel = document.getElementById('statisticsPanel');
        if (!panel) return;

        const stats = statistics;

        document.getElementById('statNTubercles').textContent = stats.n_tubercles ?? '-';
        document.getElementById('statMeanDiameter').textContent =
            stats.mean_diameter_um !== undefined
                ? `${stats.mean_diameter_um.toFixed(2)} ± ${stats.std_diameter_um?.toFixed(2) || '0.00'}`
                : '-';
        document.getElementById('statNEdges').textContent = stats.n_edges ?? '-';
        document.getElementById('statMeanSpace').textContent =
            stats.mean_space_um !== undefined
                ? `${stats.mean_space_um.toFixed(2)} ± ${stats.std_space_um?.toFixed(2) || '0.00'}`
                : '-';
        document.getElementById('statGenus').textContent = stats.suggested_genus ?? '-';
        document.getElementById('statConfidence').textContent = stats.classification_confidence ?? '-';

        // Also update the always-visible stats bar
        const statsBarTubercles = document.getElementById('statsBarTubercles');
        const statsBarDiameter = document.getElementById('statsBarDiameter');
        const statsBarEdges = document.getElementById('statsBarEdges');
        const statsBarSpace = document.getElementById('statsBarSpace');

        if (statsBarTubercles) {
            statsBarTubercles.textContent = stats.n_tubercles ?? '-';
        }
        if (statsBarDiameter) {
            statsBarDiameter.textContent = stats.mean_diameter_um !== undefined
                ? `${stats.mean_diameter_um.toFixed(2)} ± ${stats.std_diameter_um?.toFixed(2) || '0.00'}`
                : '-';
        }
        if (statsBarEdges) {
            statsBarEdges.textContent = stats.n_edges ?? '-';
        }
        if (statsBarSpace) {
            statsBarSpace.textContent = stats.mean_space_um !== undefined
                ? `${stats.mean_space_um.toFixed(2)} ± ${stats.std_space_um?.toFixed(2) || '0.00'}`
                : '-';
        }
    }

    // Highlight a tubercle row
    function highlightTubercleRow(id) {
        // Clear all highlights
        document.querySelectorAll('#tubTableBody tr').forEach(row => {
            row.classList.remove('highlighted');
        });
        document.querySelectorAll('#itcTableBody tr').forEach(row => {
            row.classList.remove('highlighted');
        });

        // Highlight the selected row
        const row = document.querySelector(`#tubTableBody tr[data-tub-id="${id}"]`);
        if (row) {
            row.classList.add('highlighted');
            row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    // Highlight an edge row
    function highlightEdgeRow(idx) {
        // Clear all highlights
        document.querySelectorAll('#tubTableBody tr').forEach(row => {
            row.classList.remove('highlighted');
        });
        document.querySelectorAll('#itcTableBody tr').forEach(row => {
            row.classList.remove('highlighted');
        });

        // Highlight the selected row
        const row = document.querySelector(`#itcTableBody tr[data-edge-idx="${idx}"]`);
        if (row) {
            row.classList.add('highlighted');
            row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    // Clear all highlights
    function clearHighlights() {
        document.querySelectorAll('#tubTableBody tr, #itcTableBody tr').forEach(row => {
            row.classList.remove('highlighted');
        });
    }

    // Get current statistics
    function getStatistics() {
        return statistics;
    }

    // Initialize
    function init() {
        // Listen for overlay selection events
        document.addEventListener('tubercleSelected', (e) => {
            highlightTubercleRow(e.detail.id);
        });

        document.addEventListener('edgeSelected', (e) => {
            highlightEdgeRow(e.detail.idx);
        });

        document.addEventListener('overlayDeselected', () => {
            clearHighlights();
        });
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        setData,
        clear,
        renderTubercleTable,
        renderEdgeTable,
        renderStatistics,
        highlightTubercleRow,
        highlightEdgeRow,
        clearHighlights,
        getStatistics,
    };
})();
