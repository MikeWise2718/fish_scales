/**
 * Fish Scale Measurement UI - Extraction Tab
 */

window.extraction = (function() {
    let isExtracting = false;
    // Note: isDirty state is now managed by sets module
    // currentTubercles/currentEdges are now stored in sets module

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

            // Mark set as dirty
            window.sets.markDirty();
            updateDirtyIndicator();

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

        return {
            n_tubercles,
            n_edges,
            mean_diameter_um,
            std_diameter_um,
            mean_space_um,
            std_space_um,
            suggested_genus: '-',
            classification_confidence: '-',
        };
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
        const extractSpinner = document.getElementById('extractSpinner');

        if (extractBtn) {
            extractBtn.disabled = isExtracting;
            extractBtn.textContent = isExtracting ? 'Extracting...' : 'Extract Tubercles and Connections';
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
        saveSlo,
        loadSlo,
        checkDirty,
        markDirty,
        confirmUnsavedChanges,
    };
})();
