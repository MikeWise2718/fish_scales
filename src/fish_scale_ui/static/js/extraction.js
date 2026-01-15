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
                const stats = await calculateStatistics(updatedTubercles, result.edges);
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

            // Record history event for auto_connect (v3.0: includes calibration)
            const calibration = window.calibration?.getCurrentCalibration();
            window.sets?.addHistoryEvent('auto_connect', {
                graph_type: graphType,
                n_tubercles: updatedTubercles.length,
                n_edges: result.edges.length,
                hexagonalness: stats.hexagonalness_score,
                cull_long_edges: cullLongEdges,
                cull_factor: cullFactor,
                calibration_um_per_pixel: calibration?.um_per_px,  // v3.0: record calibration
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

            // Store extraction parameters in the set
            window.sets.setCurrentParameters(result.parameters || params);

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

            // Record history event for extraction (v3.0: includes calibration)
            window.sets?.addHistoryEvent('extraction', {
                method: params.method || 'log',
                n_tubercles: result.statistics.n_tubercles,
                n_edges: result.statistics.n_edges,
                parameters: { ...params },
                calibration_um_per_pixel: calibration.um_per_px,  // v3.0: record calibration
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

    // Save annotations (v2 format with multiple sets)
    async function saveAnnotations(force = false) {
        try {
            // Get all sets data for v2 format
            const setsData = await window.sets.exportForSave();
            const statistics = window.data?.getStatistics() || {};

            const response = await fetch('/api/save-annotations', {
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
                    return saveAnnotations(true);
                }
                return false;
            }

            // Mark all sets as clean
            window.sets.markAllClean();
            updateDirtyIndicator();
            window.app.showToast('Annotations saved successfully', 'success');
            window.app.loadLog();
            return true;

        } catch (err) {
            console.error('Save failed:', err);
            window.app.showToast('Save failed: ' + err.message, 'error');
            return false;
        }
    }

    // Save As - prompt for custom filename
    async function saveAnnotationsAs() {
        // Get current image name as default from API
        let defaultName = 'annotations';
        try {
            const resp = await fetch('/api/current-image');
            const data = await resp.json();
            if (data.filename) {
                defaultName = data.filename.replace(/\.[^/.]+$/, '');
            }
        } catch (e) {
            console.warn('Could not fetch current image name:', e);
        }

        // Prompt for filename
        const customFilename = prompt(
            'Enter filename for annotations (without extension):',
            defaultName
        );

        if (!customFilename || !customFilename.trim()) {
            return false; // User cancelled
        }

        // Sanitize filename
        const sanitized = customFilename.trim().replace(/[\/\\:*?"<>|]/g, '');
        if (!sanitized) {
            window.app.showToast('Invalid filename', 'error');
            return false;
        }

        try {
            // Get all sets data for v2 format
            const setsData = await window.sets.exportForSave();
            const statistics = window.data?.getStatistics() || {};

            const response = await fetch('/api/save-annotations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    force: true, // Always force for Save As (new filename)
                    version: 2,
                    ...setsData,
                    statistics,
                    custom_filename: sanitized,
                }),
            });

            const result = await response.json();

            if (result.error) {
                window.app.showToast(result.error, 'error');
                return false;
            }

            // Note: Don't mark as clean since this is a copy
            window.app.showToast(`Annotations saved as ${sanitized}`, 'success');
            window.app.loadLog();
            return true;

        } catch (err) {
            console.error('Save As failed:', err);
            window.app.showToast('Save As failed: ' + err.message, 'error');
            return false;
        }
    }

    // Load annotations (supports both v1 and v2 formats)
    async function loadAnnotations(path = null) {
        try {
            const response = await fetch('/api/load-annotations', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path }),
            });

            const result = await response.json();

            if (result.error) {
                if (result.error.includes('not found')) {
                    // No existing annotations - that's OK, initialize with default set
                    window.sets.init();
                    return false;
                }
                window.app.showToast(result.error, 'error');
                return false;
            }

            // Check name match warning
            if (!result.name_match) {
                window.app.showToast('Warning: Annotations were saved for a different image', 'warning');
            }

            // Check for v2/v3 format (has sets array)
            if (result.data?.version >= 2 && result.data?.sets) {
                // V2/V3 format - load multiple sets
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
                const stats = await calculateStatistics(currentSet.tubercles, currentSet.edges);
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
            window.app.showToast('Annotations loaded successfully', 'success');
            window.app.loadLog();
            return true;

        } catch (err) {
            console.error('Load failed:', err);
            return false;
        }
    }

    // Calculate statistics from data (async - fetches hexagonalness from server)
    async function calculateStatistics(tubercles, edges) {
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

        // Fetch hexagonalness metrics from server
        const hexMetrics = await calculateHexagonalness();

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

    // Fetch hexagonalness metrics from server API
    async function calculateHexagonalness() {
        const defaultResult = {
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

        try {
            // Get weights from settings
            const spacingWeight = window.settings?.get('hexSpacingWeight') ?? 0.40;
            const degreeWeight = window.settings?.get('hexDegreeWeight') ?? 0.45;
            const edgeRatioWeight = window.settings?.get('hexEdgeRatioWeight') ?? 0.15;

            const params = new URLSearchParams({
                spacing_weight: spacingWeight,
                degree_weight: degreeWeight,
                edge_ratio_weight: edgeRatioWeight,
            });

            const response = await fetch(`/api/hexagonalness?${params}`);
            if (!response.ok) {
                console.error('Hexagonalness API error:', response.status);
                return defaultResult;
            }

            return await response.json();
        } catch (err) {
            console.error('Hexagonalness calculation failed:', err);
            return defaultResult;
        }
    }

    // Show overwrite confirmation dialog with comparison
    async function showOverwriteDialog(files) {
        // Fetch existing file info for comparison
        let existingInfo = null;
        try {
            const resp = await fetch('/api/annotation-info');
            existingInfo = await resp.json();
        } catch (e) {
            console.warn('Could not fetch annotation info:', e);
        }

        // Get current data info
        const currentSets = window.sets?.getSetList() || [];
        let currentTotalTub = 0;
        let currentTotalEdge = 0;
        currentSets.forEach(s => {
            const set = window.sets?.getSet(s.id);
            if (set) {
                currentTotalTub += (set.tubercles?.length || 0);
                currentTotalEdge += (set.edges?.length || 0);
            }
        });

        // Build comparison HTML
        let html = '<div class="overwrite-comparison" style="display: flex; gap: 20px; flex-wrap: wrap;">';

        // Current data (what will be saved)
        html += '<div class="comparison-section" style="flex: 1; min-width: 200px; padding: 10px; background: #e8f5e9; border-radius: 4px;">';
        html += '<h4 style="margin-top: 0; color: #2e7d32;">Data to Save</h4>';
        html += `<p><strong>Sets:</strong> ${currentSets.length}</p>`;
        if (currentSets.length > 0) {
            html += '<ul style="margin: 5px 0; padding-left: 20px;">';
            currentSets.forEach(s => {
                const set = window.sets?.getSet(s.id);
                const nTub = set?.tubercles?.length || 0;
                const nEdge = set?.edges?.length || 0;
                html += `<li>${s.name}: ${nTub} tub, ${nEdge} conn</li>`;
            });
            html += '</ul>';
        }
        html += `<p><strong>Total:</strong> ${currentTotalTub} tubercles, ${currentTotalEdge} connections</p>`;
        html += '</div>';

        // Existing file data (what will be overwritten)
        html += '<div class="comparison-section" style="flex: 1; min-width: 200px; padding: 10px; background: #ffebee; border-radius: 4px;">';
        html += '<h4 style="margin-top: 0; color: #c62828;">Will Be Overwritten</h4>';
        if (existingInfo?.exists && !existingInfo.error) {
            const modified = new Date(existingInfo.modified).toLocaleString();
            const sizeKB = (existingInfo.file_size / 1024).toFixed(1);
            html += `<p><strong>File:</strong> ${existingInfo.path}</p>`;
            html += `<p><strong>Modified:</strong> ${modified}</p>`;
            html += `<p><strong>Size:</strong> ${sizeKB} KB</p>`;
            html += `<p><strong>Sets:</strong> ${existingInfo.n_sets}</p>`;
            if (existingInfo.sets && existingInfo.sets.length > 0) {
                html += '<ul style="margin: 5px 0; padding-left: 20px;">';
                existingInfo.sets.forEach(s => {
                    html += `<li>${s.name}: ${s.n_tubercles} tub, ${s.n_edges} conn</li>`;
                });
                html += '</ul>';
            }
            html += `<p><strong>Total:</strong> ${existingInfo.total_tubercles} tubercles, ${existingInfo.total_edges} connections</p>`;
        } else {
            html += '<p><em>Could not read file details</em></p>';
            html += `<p>Files: ${files.join(', ')}</p>`;
        }
        html += '</div>';

        html += '</div>';

        // Add warning if losing data
        if (existingInfo?.exists && existingInfo.total_tubercles > currentTotalTub) {
            const diff = existingInfo.total_tubercles - currentTotalTub;
            html += `<p style="color: #c00; margin-top: 15px; font-weight: bold;">`;
            html += `Warning: You will lose ${diff} tubercle${diff !== 1 ? 's' : ''} by overwriting.`;
            html += '</p>';
        }

        return new Promise((resolve) => {
            window.app.showModal(
                'Overwrite Existing Annotations?',
                html,
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

        // Update Save Annotations button
        const saveBtn = document.getElementById('saveAnnotationsBtn');
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

        // Save Annotations button (in toolbar)
        const saveAnnotationsBtn = document.getElementById('saveAnnotationsBtn');
        if (saveAnnotationsBtn) {
            saveAnnotationsBtn.addEventListener('click', () => saveAnnotations());
        }

        // Keyboard shortcut: Ctrl+S
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                saveAnnotations();
            }
        });

        // Warn on page unload
        window.addEventListener('beforeunload', (e) => {
            if (checkDirty()) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes.';
                return e.returnValue;
            }
        });

        // Listen for data modification events from editor
        document.addEventListener('dataModified', () => {
            markDirty();
        });

        // Check for existing annotations on image load
        document.addEventListener('imageLoaded', () => {
            loadAnnotations().then(loaded => {
                if (!loaded) {
                    // Clear previous data if no annotations found
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
        saveAnnotations,
        saveAnnotationsAs,
        loadAnnotations,
        // Backwards compatibility aliases
        saveSlo: saveAnnotations,
        saveSloAs: saveAnnotationsAs,
        loadSlo: loadAnnotations,
        checkDirty,
        markDirty,
        confirmUnsavedChanges,
        calculateHexagonalness,
    };
})();
