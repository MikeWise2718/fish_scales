/**
 * Fish Scale Measurement UI - Extraction Tab
 */

window.extraction = (function() {
    let isExtracting = false;
    let isDirty = false;
    let currentTubercles = [];
    let currentEdges = [];

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

            // Store current data
            currentTubercles = result.tubercles;
            currentEdges = result.edges;

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

            // Clear undo history on new extraction
            if (window.undoManager) {
                window.undoManager.clear();
            }

            // Mark params as extracted
            if (window.configure) {
                window.configure.markExtracted(result.parameters);
            }

            // Update dirty state
            isDirty = true;
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

    // Save SLO
    async function saveSlo(force = false) {
        try {
            // Get current data from editor (includes any manual edits)
            const editorData = window.editor?.getData() || {};
            const statistics = window.data?.getStatistics() || {};

            const response = await fetch('/api/save-slo', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    force,
                    tubercles: editorData.tubercles || currentTubercles,
                    edges: editorData.edges || currentEdges,
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

            isDirty = false;
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

    // Load SLO
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
                    // No existing SLO - that's OK
                    return false;
                }
                window.app.showToast(result.error, 'error');
                return false;
            }

            // Check name match warning
            if (!result.name_match) {
                window.app.showToast('Warning: SLO was saved for a different image', 'warning');
            }

            // Update overlay
            if (window.overlay && result.data) {
                window.overlay.setData(result.data.tubercles, result.data.edges);
            }

            // Update data tables
            if (window.data && result.data) {
                window.data.setData(result.data.tubercles, result.data.edges, result.data.statistics);
            }

            // Update calibration display
            if (result.data?.calibration && window.calibration) {
                window.calibration.setCalibration(result.data.calibration);
            }

            // Update editor with loaded data
            if (window.editor && result.data) {
                window.editor.setData(result.data.tubercles, result.data.edges);
            }

            // Clear undo history on load
            if (window.undoManager) {
                window.undoManager.clear();
            }

            isDirty = false;
            updateDirtyIndicator();
            window.app.showToast('SLO loaded successfully', 'success');
            window.app.loadLog();
            return true;

        } catch (err) {
            console.error('Load failed:', err);
            return false;
        }
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
        return isDirty;
    }

    // Confirm navigation with unsaved changes
    function confirmUnsavedChanges() {
        if (!isDirty) return true;
        return confirm('You have unsaved changes. Are you sure you want to leave?');
    }

    // Mark as dirty (called by editor)
    function markDirty() {
        isDirty = true;
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
