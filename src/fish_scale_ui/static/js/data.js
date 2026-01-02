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
                statsBarHex.textContent = hexScore.toFixed(3);
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

    // ===== History Rendering =====

    let historyCollapsed = false;

    /**
     * Render the history timeline for the current set
     */
    function renderHistory() {
        const timeline = document.getElementById('historyTimeline');
        const empty = document.getElementById('historyEmpty');
        if (!timeline || !empty) return;

        const history = window.sets?.getHistory() || [];

        if (history.length === 0) {
            empty.style.display = 'block';
            timeline.style.display = 'none';
            timeline.innerHTML = '';
            return;
        }

        empty.style.display = 'none';
        timeline.style.display = 'block';

        // Render events in reverse chronological order
        timeline.innerHTML = history.slice().reverse().map(event => renderHistoryEvent(event)).join('');

        // Bind restore buttons
        timeline.querySelectorAll('.history-event-restore').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const params = JSON.parse(btn.dataset.params);
                restoreParameters(params);
            });
        });
    }

    /**
     * Render a single history event
     */
    function renderHistoryEvent(event) {
        const time = formatEventTime(event.timestamp);
        const typeLabel = formatEventType(event.type);
        const details = formatEventDetails(event);

        // Check if this event has restorable parameters
        const hasParams = event.type === 'extraction' && event.parameters;
        const restoreBtn = hasParams
            ? `<a href="#" class="history-event-restore" data-params='${JSON.stringify(event.parameters)}'>Restore params</a>`
            : '';

        return `
            <div class="history-event" data-type="${event.type}">
                <div class="history-event-header">
                    <span class="history-event-type">${typeLabel}</span>
                    <span class="history-event-time">${time}</span>
                    <span class="history-event-user">${event.user || 'Unknown'}</span>
                </div>
                ${details ? `<div class="history-event-details">${details}</div>` : ''}
                ${restoreBtn}
            </div>
        `;
    }

    /**
     * Format event timestamp for display
     */
    function formatEventTime(timestamp) {
        if (!timestamp) return '';
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString();
    }

    /**
     * Format event type for display
     */
    function formatEventType(type) {
        const labels = {
            extraction: 'Extraction',
            auto_connect: 'Auto Connect',
            manual_edit: 'Manual Edit',
            agent_phase: 'Agent',
            clone: 'Cloned',
            import: 'Import',
        };
        return labels[type] || type;
    }

    /**
     * Format event details for display
     */
    function formatEventDetails(event) {
        switch (event.type) {
            case 'extraction':
                return `${event.n_tubercles} tubercles, ${event.n_edges} connections (${event.method || 'auto'})`;
            case 'auto_connect':
                return `${event.n_edges} connections (${event.graph_type || 'auto'})`;
            case 'manual_edit':
                return event.summary || '';
            case 'agent_phase':
                return `Phase ${event.phase}: ${event.summary || ''}`;
            case 'clone':
                return `from "${event.source_set_name}"`;
            case 'import':
                return event.source || '';
            default:
                return '';
        }
    }

    /**
     * Restore extraction parameters from a history event
     */
    function restoreParameters(params) {
        if (!window.configure) {
            window.app?.showToast('Configure module not loaded', 'error');
            return;
        }

        window.configure.setParams(params);
        window.app?.showToast('Parameters restored', 'success');

        // Switch to Configure tab
        const configBtn = document.querySelector('[data-tab="configure"]');
        if (configBtn) configBtn.click();
    }

    /**
     * Toggle history section collapsed state
     */
    function toggleHistory() {
        const section = document.querySelector('.history-section');
        if (!section) return;

        historyCollapsed = !historyCollapsed;
        section.classList.toggle('collapsed', historyCollapsed);
    }

    /**
     * Initialize history UI
     */
    function initHistory() {
        const header = document.getElementById('historyHeader');
        if (header) {
            header.addEventListener('click', toggleHistory);
        }

        // Listen for set changes and history updates
        document.addEventListener('setChanged', renderHistory);
        document.addEventListener('setsLoaded', renderHistory);
        document.addEventListener('historyChanged', renderHistory);

        // Initial render
        renderHistory();
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', () => {
        init();
        initHistory();
    });

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
        renderHistory,
    };
})();
