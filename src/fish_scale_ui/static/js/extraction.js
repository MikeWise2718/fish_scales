/**
 * Fish Scale Measurement UI - Extraction Tab
 */

window.extraction = (function() {
    let isExtracting = false;
    // Note: isDirty state is now managed by sets module
    // currentTubercles/currentEdges are now stored in sets module

    // Run connection regeneration only (keeps existing tubercles)
    async function runConnectionExtraction() {
        if (isExtracting) return;

        // Check calibration
        const calibration = window.calibration?.getCurrentCalibration();
        if (!calibration || !calibration.um_per_px) {
            window.app.showToast('Please set calibration first', 'warning');
            return;
        }

        // Get current tubercles
        const currentSet = window.sets?.getCurrentSet();
        if (!currentSet || !currentSet.tubercles || currentSet.tubercles.length < 2) {
            window.app.showToast('Need at least 2 tubercles to generate connections', 'warning');
            return;
        }

        // Get graph type and culling params from configure
        const params = window.configure?.getParams() || {};
        const graphType = params.neighbor_graph || 'gabriel';
        const cullLongEdges = params.cull_long_edges !== undefined ? params.cull_long_edges : true;
        const cullFactor = params.cull_factor || 1.8;

        isExtracting = true;
        updateUI();

        try {
            const response = await fetch('/api/regenerate-connections', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tubercles: currentSet.tubercles,
                    graph_type: graphType,
                    cull_long_edges: cullLongEdges,
                    cull_factor: cullFactor,
                }),
            });

            const result = await response.json();

            if (result.error) {
                window.app.showToast(result.error, 'error');
                return;
            }

            // Use updated tubercles with boundary flags from API
            const updatedTubercles = result.tubercles || currentSet.tubercles;

            // Update data in sets module
            window.sets.setCurrentData(updatedTubercles, result.edges);

            // Update overlay
            if (window.overlay) {
                window.overlay.setData(updatedTubercles, result.edges);
            }

            // Update data tables with new statistics
            if (window.data) {
                const stats = calculateStatistics(updatedTubercles, result.edges);
                // Include boundary counts from API response
                if (result.statistics) {
                    stats.n_boundary = result.statistics.n_boundary;
                    stats.n_interior = result.statistics.n_interior;
                }
                window.data.setData(updatedTubercles, result.edges, stats);
            }

            // Update editor
            if (window.editor) {
                window.editor.setData(updatedTubercles, result.edges);
            }

            // Record history event for auto_connect
            window.sets?.addHistoryEvent('auto_connect', {
                graph_type: graphType,
                n_tubercles: updatedTubercles.length,
                n_edges: result.edges.length,
                hexagonalness: stats.hexagonalness_score,
                cull_long_edges: cullLongEdges,
                cull_factor: cullFactor,
            });

            // Mark set as dirty
            window.sets.markDirty();
            updateDirtyIndicator();

            // Dispatch event
            document.dispatchEvent(new CustomEvent('connectionsRegenerated', {
                detail: {
                    tubercles: updatedTubercles,
                    edges: result.edges,
                }
            }));

            // Show success message
            window.app.showToast(
                `Regenerated ${result.edges.length} connections using ${graphType}`,
                'success'
            );

            // Refresh log
            window.app.loadLog();

        } catch (err) {
            console.error('Connection extraction failed:', err);
            window.app.showToast('Connection extraction failed: ' + err.message, 'error');
        } finally {
            isExtracting = false;
            updateUI();
        }
    }

    // Run extraction
    async function runExtraction() {
        if (isExtracting) return;

        // Check calibration
        const calibration = window.calibration?.getCurrentCalibration();
        if (!calibration || !calibration.um_per_px) {
            window.app.showToast('Please set calibration first', 'warning');
            return;
        }

        // Get parameters from configure tab
        const params = window.configure?.getParams() || {};

        isExtracting = true;
        updateUI();

        try {
            const response = await fetch('/api/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params),
            });

            const result = await response.json();

            if (result.error) {
                window.app.showToast(result.error, 'error');
                return;
            }

            // Store data in sets module
            window.sets.setCurrentData(result.tubercles, result.edges);

            // Update overlay
            if (window.overlay) {
                window.overlay.setData(result.tubercles, result.edges);
            }

            // Update data tables
            if (window.data) {
                window.data.setData(result.tubercles, result.edges, result.statistics);
            }

            // Update editor with extracted data
            if (window.editor) {
                window.editor.setData(result.tubercles, result.edges);
            }

            // Clear undo/redo for current set
            window.sets.clearUndoRedo();

            // Mark params as extracted
            if (window.configure) {
                window.configure.markExtracted(result.parameters);
            }

            // Record history event for extraction
            window.sets?.addHistoryEvent('extraction', {
                method: params.method || 'log',
                n_tubercles: result.statistics.n_tubercles,
                n_edges: result.statistics.n_edges,
                parameters: { ...params },
            });

            // Mark set as dirty
            window.sets.markDirty();
            updateDirtyIndicator();

            // Log extraction event
            window.app.logEvent('extraction', {
                params: params,
                result: {
                    n_tubercles: result.statistics.n_tubercles,
                    n_edges: result.statistics.n_edges,
                    hexagonalness: result.statistics.hexagonalness_score,
                    mean_diameter_um: result.statistics.mean_diameter_um,
                    mean_space_um: result.statistics.mean_space_um,
                }
            });

            // Dispatch event for editor
            document.dispatchEvent(new CustomEvent('extractionComplete', {
                detail: {
                    tubercles: result.tubercles,
                    edges: result.edges,
                    statistics: result.statistics,
                }
            }));

            // Show success message
            window.app.showToast(
                `Extracted ${result.statistics.n_tubercles} tubercles, ${result.statistics.n_edges} connections`,
                'success'
            );

            // Refresh log
            window.app.loadLog();

        } catch (err) {
            console.error('Extraction failed:', err);
            window.app.showToast('Extraction failed: ' + err.message, 'error');
        } finally {
            isExtracting = false;
            updateUI();
        }
    }

    // Save SLO (v2 format with multiple sets)
    async function saveSlo(force = false) {
        try {
            // Get all sets data for v2 format
            const setsData = window.sets.exportForSave();
            const statistics = window.data?.getStatistics() || {};

            const response = await fetch('/api/save-slo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    force,
                    version: 2,
                    ...setsData,
                    statistics,
                }),
            });

            const result = await response.json();

            if (result.error) {
                window.app.showToast(result.error, 'error');
                return false;
            }

            // Check for existing files warning
            if (result.existing_files && result.existing_files.length > 0 && !force) {
                const confirmed = await showOverwriteDialog(result.existing_files);
                if (confirmed) {
                    return saveSlo(true);
                }
                return false;
            }

            // Mark all sets as clean
            window.sets.markAllClean();
            updateDirtyIndicator();
            window.app.showToast('SLO saved successfully', 'success');
            window.app.loadLog();
            return true;

        } catch (err) {
            console.error('Save failed:', err);
            window.app.showToast('Save failed: ' + err.message, 'error');
            return false;
        }
    }

    // Load SLO (supports both v1 and v2 formats)
    async function loadSlo(path = null) {
        try {
            const response = await fetch('/api/load-slo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path }),
            });

            const result = await response.json();

            if (result.error) {
                if (result.error.includes('not found')) {
                    // No existing SLO - that's OK, initialize with default set
                    window.sets.init();
                    return false;
                }
                window.app.showToast(result.error, 'error');
                return false;
            }

            // Check name match warning
            if (!result.name_match) {
                window.app.showToast('Warning: SLO was saved for a different image', 'warning');
            }

            // Check for v2 format (has sets array)
            if (result.data?.version === 2 && result.data?.sets) {
                // V2 format - load multiple sets
                window.sets.importFromLoad(result.data);
            } else if (result.data?.tubercles) {
                // V1 format - convert to single set
                window.sets.importFromV1(result.data.tubercles, result.data.edges || []);
            } else {
                // Empty or invalid - initialize fresh
                window.sets.init();
            }

            // Get current set data
            const currentSet = window.sets.getCurrentSet();

            // Update overlay
            if (window.overlay && currentSet) {
                window.overlay.setData(currentSet.tubercles, currentSet.edges);
            }

            // Update data tables
            if (window.data && currentSet) {
                // Calculate statistics from current set
                const stats = calculateStatistics(currentSet.tubercles, currentSet.edges);
                window.data.setData(currentSet.tubercles, currentSet.edges, stats);
            }

            // Update calibration display
            if (result.data?.calibration && window.calibration) {
                window.calibration.setCalibration(result.data.calibration);
            }

            // Update editor with loaded data
            if (window.editor && currentSet) {
                window.editor.setData(currentSet.tubercles, currentSet.edges);
            }

            updateDirtyIndicator();
            window.app.showToast('SLO loaded successfully', 'success');
            window.app.loadLog();
            return true;

        } catch (err) {
            console.error('Load failed:', err);
            return false;
        }
    }

    // Calculate statistics from data
    function calculateStatistics(tubercles, edges) {
        const n_tubercles = tubercles.length;
        const n_edges = edges.length;

        let mean_diameter_um = 0;
        let std_diameter_um = 0;
        let mean_space_um = 0;
        let std_space_um = 0;

        if (n_tubercles > 0) {
            const diameters = tubercles.map(t => t.diameter_um);
            mean_diameter_um = diameters.reduce((a, b) => a + b, 0) / n_tubercles;
            if (n_tubercles > 1) {
                const variance = diameters.reduce((sum, d) =>
                    sum + Math.pow(d - mean_diameter_um, 2), 0) / (n_tubercles - 1);
                std_diameter_um = Math.sqrt(variance);
            }
        }

        if (n_edges > 0) {
            const spaces = edges.map(e => e.edge_distance_um);
            mean_space_um = spaces.reduce((a, b) => a + b, 0) / n_edges;
            if (n_edges > 1) {
                const variance = spaces.reduce((sum, s) =>
                    sum + Math.pow(s - mean_space_um, 2), 0) / (n_edges - 1);
                std_space_um = Math.sqrt(variance);
            }
        }

        // Calculate hexagonalness metrics
        const hexMetrics = calculateHexagonalness(tubercles, edges);

        // Count boundary vs interior nodes
        const n_boundary = tubercles.filter(t => t.is_boundary).length;
        const n_interior = n_tubercles - n_boundary;

        return {
            n_tubercles,
            n_edges,
            n_boundary,
            n_interior,
            mean_diameter_um,
            std_diameter_um,
            mean_space_um,
            std_space_um,
            suggested_genus: '-',
            classification_confidence: '-',
            ...hexMetrics,
        };
    }

    // Calculate hexagonalness metrics
    function calculateHexagonalness(tubercles, edges) {
        const MIN_NODES_FOR_RELIABLE = 15;

        const result = {
            hexagonalness_score: 0.0,
            spacing_uniformity: 0.0,
            degree_score: 0.0,
            edge_ratio_score: 0.0,
            mean_degree: 0.0,
            spacing_cv: 1.0,
            reliability: 'none',
            n_nodes: 0,
            n_interior_nodes: 0,
        };

        if (!tubercles || tubercles.length < 4) {
            return result;
        }

        const n_nodes = tubercles.length;
        result.n_nodes = n_nodes;

        // Separate interior and boundary nodes
        const interiorTubercles = tubercles.filter(t => !t.is_boundary);
        const interiorIds = new Set(interiorTubercles.map(t => t.id));
        const n_interior = interiorIds.size;
        result.n_interior_nodes = n_interior;

        // Reliability based on interior node count
        result.reliability = n_interior >= MIN_NODES_FOR_RELIABLE ? 'high' : (n_interior >= 4 ? 'low' : 'none');

        // Spacing uniformity - uses all edges
        if (edges && edges.length > 0) {
            const spacings = edges.map(e => e.edge_distance_um).filter(s => s > 0);
            if (spacings.length > 0) {
                const mean = spacings.reduce((a, b) => a + b, 0) / spacings.length;
                const variance = spacings.reduce((sum, s) => sum + Math.pow(s - mean, 2), 0) / spacings.length;
                const cv = mean > 0 ? Math.sqrt(variance) / mean : 1.0;
                result.spacing_cv = cv;
                result.spacing_uniformity = Math.max(0, 1 - 2 * cv);
            }
        }

        // Degree distribution - INTERIOR NODES ONLY
        const degree = {};
        tubercles.forEach(t => { degree[t.id] = 0; });
        edges.forEach(e => {
            const aId = e.tubercle_a_id ?? e.id1;
            const bId = e.tubercle_b_id ?? e.id2;
            if (degree[aId] !== undefined) degree[aId]++;
            if (degree[bId] !== undefined) degree[bId]++;
        });

        // Filter to interior nodes only
        const interiorDegrees = interiorTubercles.map(t => degree[t.id]);
        if (interiorDegrees.length > 0) {
            result.mean_degree = interiorDegrees.reduce((a, b) => a + b, 0) / interiorDegrees.length;
            let weightedScore = 0;
            interiorDegrees.forEach(d => {
                if (d >= 5 && d <= 7) weightedScore += 1.0;
                else if (d === 4 || d === 8) weightedScore += 0.7;
                else if (d === 3 || d === 9) weightedScore += 0.3;
            });
            result.degree_score = weightedScore / interiorDegrees.length;
        }

        // Edge/node ratio - uses interior nodes
        if (n_interior > 0) {
            const ratio = edges.length / n_interior;
            result.edge_ratio_score = Math.max(0, 1 - Math.abs(ratio - 3.0) / 2);
        }

        // Composite score (use configurable weights from settings)
        const spacingWeight = window.settings?.get('hexSpacingWeight') ?? 0.40;
        const degreeWeight = window.settings?.get('hexDegreeWeight') ?? 0.45;
        const edgeRatioWeight = window.settings?.get('hexEdgeRatioWeight') ?? 0.15;

        result.hexagonalness_score = (
            spacingWeight * result.spacing_uniformity +
            degreeWeight * result.degree_score +
            edgeRatioWeight * result.edge_ratio_score
        );

        return result;
    }

    // Show overwrite confirmation dialog
    function showOverwriteDialog(files) {
        return new Promise((resolve) => {
            window.app.showModal(
                'Overwrite Files?',
                `<p>The following files already exist:</p><ul>${files.map(f => `<li>${f}</li>`).join('')}</ul><p>Do you want to overwrite them?</p>`,
                [
                    { text: 'Cancel', action: () => resolve(false) },
                    { text: 'Overwrite', primary: true, action: () => resolve(true) },
                ]
            );
        });
    }

    // Update UI state
    function updateUI() {
        const extractBtn = document.getElementById('extractBtn');
        const extractConnectionsBtn = document.getElementById('extractConnectionsBtn');
        const extractSpinner = document.getElementById('extractSpinner');

        if (extractBtn) {
            extractBtn.disabled = isExtracting;
            extractBtn.textContent = isExtracting ? 'Extracting...' : 'Extract Tubercles + Connections';
        }
        if (extractConnectionsBtn) {
            extractConnectionsBtn.disabled = isExtracting;
        }
        if (extractSpinner) {
            extractSpinner.style.display = isExtracting ? 'inline-block' : 'none';
        }
    }

    // Update dirty indicator
    function updateDirtyIndicator() {
        const isDirty = window.sets?.anyUnsavedChanges() || false;

        // Extraction tab indicator
        const indicator = document.getElementById('unsavedIndicator');
        if (indicator) {
            indicator.style.display = isDirty ? 'inline-block' : 'none';
        }

        // Image tab indicator
        const indicatorImage = document.getElementById('unsavedIndicatorImage');
        if (indicatorImage) {
            indicatorImage.style.display = isDirty ? 'inline-block' : 'none';
        }

        // Update Save SLO button
        const saveBtn = document.getElementById('saveSloBtn');
        if (saveBtn) {
            saveBtn.classList.toggle('has-changes', isDirty);
        }
    }

    // Check dirty state
    function checkDirty() {
        return window.sets?.anyUnsavedChanges() || false;
    }

    // Confirm navigation with unsaved changes
    function confirmUnsavedChanges() {
        if (!checkDirty()) return true;
        return confirm('You have unsaved changes. Are you sure you want to leave?');
    }

    // Mark as dirty (called by editor)
    function markDirty() {
        window.sets?.markDirty();
        updateDirtyIndicator();
    }

    // Initialize
    function init() {
        // Extract button
        const extractBtn = document.getElementById('extractBtn');
        if (extractBtn) {
            extractBtn.addEventListener('click', runExtraction);
        }

        // Extract Connections Only button
        const extractConnectionsBtn = document.getElementById('extractConnectionsBtn');
        if (extractConnectionsBtn) {
            extractConnectionsBtn.addEventListener('click', runConnectionExtraction);
        }

        // Save SLO button (in toolbar)
        const saveSloBtn = document.getElementById('saveSloBtn');
        if (saveSloBtn) {
            saveSloBtn.addEventListener('click', () => saveSlo());
        }

        // Load SLO button
        const loadSloBtn = document.getElementById('loadSloBtn');
        if (loadSloBtn) {
            loadSloBtn.addEventListener('click', () => loadSlo());
        }

        // Keyboard shortcut: Ctrl+S
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                saveSlo();
            }
        });

        // Warn on page unload
        window.addEventListener('beforeunload', (e) => {
            if (isDirty) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes.';
                return e.returnValue;
            }
        });

        // Listen for data modification events from editor
        document.addEventListener('dataModified', () => {
            markDirty();
        });

        // Check for existing SLO on image load
        document.addEventListener('imageLoaded', () => {
            loadSlo().then(loaded => {
                if (!loaded) {
                    // Clear previous data if no SLO found
                    if (window.overlay) window.overlay.clear();
                    if (window.data) window.data.clear();
                    if (window.editor) window.editor.setData([], []);
                }
            });
        });
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        runExtraction,
        runConnectionExtraction,
        saveSlo,
        loadSlo,
        checkDirty,
        markDirty,
        confirmUnsavedChanges,
        calculateHexagonalness,
    };
})();
