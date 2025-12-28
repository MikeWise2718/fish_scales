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
            row.innerHTML = '<td colspan="6" class="empty-table">No tubercles detected</td>';
            tbody.appendChild(row);
            return;
        }

        tubercles.forEach(tub => {
            const row = document.createElement('tr');
            row.dataset.tubId = tub.id;
            const boundaryStr = tub.is_boundary ? 'Y' : 'N';
            row.innerHTML = `
                <td>${tub.id}</td>
                <td>${tub.centroid_x.toFixed(1)}</td>
                <td>${tub.centroid_y.toFixed(1)}</td>
                <td>${tub.diameter_um.toFixed(2)}</td>
                <td>${(tub.circularity * 100).toFixed(1)}%</td>
                <td>${boundaryStr}</td>
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

        // Show boundary/interior breakdown if available
        const boundaryDetailEl = document.getElementById('statBoundaryDetail');
        if (boundaryDetailEl) {
            if (stats.n_boundary !== undefined && stats.n_interior !== undefined) {
                boundaryDetailEl.textContent = `(${stats.n_interior} interior, ${stats.n_boundary} boundary)`;
            } else {
                boundaryDetailEl.textContent = '';
            }
        }

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

        // Hexagonalness metrics
        const hexScoreEl = document.getElementById('statHexScore');
        const hexReliabilityEl = document.getElementById('statHexReliability');
        if (hexScoreEl) {
            const hexScore = stats.hexagonalness_score;
            const reliability = stats.reliability;
            if (hexScore !== undefined) {
                hexScoreEl.textContent = hexScore.toFixed(3);
                // Color code: green (>0.7), yellow (0.4-0.7), red (<0.4)
                hexScoreEl.classList.remove('score-good', 'score-medium', 'score-poor');
                if (hexScore >= 0.7) {
                    hexScoreEl.classList.add('score-good');
                } else if (hexScore >= 0.4) {
                    hexScoreEl.classList.add('score-medium');
                } else {
                    hexScoreEl.classList.add('score-poor');
                }
            } else {
                hexScoreEl.textContent = '-';
                hexScoreEl.classList.remove('score-good', 'score-medium', 'score-poor');
            }

            // Show reliability indicator
            if (hexReliabilityEl) {
                hexReliabilityEl.classList.remove('reliability-high', 'reliability-low', 'reliability-none');
                if (reliability === 'low') {
                    hexReliabilityEl.textContent = `(${stats.n_nodes || 0} nodes - low confidence)`;
                    hexReliabilityEl.classList.add('reliability-low');
                } else if (reliability === 'none') {
                    hexReliabilityEl.textContent = '(insufficient data)';
                    hexReliabilityEl.classList.add('reliability-none');
                } else {
                    hexReliabilityEl.textContent = '';
                }
            }
        }

        // Formula component scores
        const spacingUniformityEl = document.getElementById('statSpacingUniformity');
        if (spacingUniformityEl) {
            spacingUniformityEl.textContent = stats.spacing_uniformity !== undefined
                ? stats.spacing_uniformity.toFixed(3)
                : '-';
        }

        const degreeScoreEl = document.getElementById('statDegreeScore');
        if (degreeScoreEl) {
            degreeScoreEl.textContent = stats.degree_score !== undefined
                ? stats.degree_score.toFixed(3)
                : '-';
        }

        const edgeRatioScoreEl = document.getElementById('statEdgeRatioScore');
        if (edgeRatioScoreEl) {
            edgeRatioScoreEl.textContent = stats.edge_ratio_score !== undefined
                ? stats.edge_ratio_score.toFixed(3)
                : '-';
        }

        // Supporting raw metrics
        const spacingCVEl = document.getElementById('statSpacingCV');
        if (spacingCVEl) {
            spacingCVEl.textContent = stats.spacing_cv !== undefined
                ? stats.spacing_cv.toFixed(3)
                : '-';
        }

        const meanDegreeEl = document.getElementById('statMeanDegree');
        if (meanDegreeEl) {
            meanDegreeEl.textContent = stats.mean_degree !== undefined
                ? stats.mean_degree.toFixed(2)
                : '-';
        }

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

        // Update hex score in stats bar
        const statsBarHex = document.getElementById('statsBarHex');
        if (statsBarHex) {
            const hexScore = stats.hexagonalness_score;
            const reliability = stats.reliability;
            if (hexScore !== undefined && reliability !== 'none') {
                statsBarHex.textContent = hexScore.toFixed(2);
                statsBarHex.classList.toggle('hex-low', reliability === 'low');
            } else {
                statsBarHex.textContent = '-';
                statsBarHex.classList.remove('hex-low');
            }
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

        // Help icons for hexagonalness metrics
        const helpIcons = document.querySelectorAll('.help-icon[data-help]');
        helpIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                e.preventDefault();
                const topic = icon.dataset.help;
                window.open(`/static/help/hexagonalness.html#${topic}`, 'help', 'width=800,height=600');
            });
        });

        // Update weight displays when settings change or on init
        updateWeightDisplays();
        window.addEventListener('hexWeightsChanged', updateWeightDisplays);
    }

    // Update the weight percentage displays in the Data tab
    function updateWeightDisplays() {
        const spacingWeight = window.settings?.get('hexSpacingWeight') ?? 0.40;
        const degreeWeight = window.settings?.get('hexDegreeWeight') ?? 0.45;
        const edgeRatioWeight = window.settings?.get('hexEdgeRatioWeight') ?? 0.15;

        const spacingEl = document.getElementById('statSpacingWeight');
        const degreeEl = document.getElementById('statDegreeWeight');
        const edgeRatioEl = document.getElementById('statEdgeRatioWeight');

        if (spacingEl) spacingEl.textContent = `(${Math.round(spacingWeight * 100)}%)`;
        if (degreeEl) degreeEl.textContent = `(${Math.round(degreeWeight * 100)}%)`;
        if (edgeRatioEl) edgeRatioEl.textContent = `(${Math.round(edgeRatioWeight * 100)}%)`;
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
