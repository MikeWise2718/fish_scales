/**
 * Fish Scale Measurement UI - Set Selector UI
 * Handles the UI for multiple annotation sets
 */

window.setUI = (function() {
    let menuOpen = false;

    /**
     * Initialize the set selector UI
     */
    function init() {
        // Render initial set buttons
        renderSetButtons();

        // Bind button handlers
        bindHandlers();

        // Listen for set events
        bindSetEvents();

        // Update stats bar set name
        updateStatsBarSetName();
    }

    /**
     * Render the set buttons in the selector bar
     */
    function renderSetButtons() {
        const container = document.getElementById('setButtons');
        if (!container) return;

        const setList = window.sets.getSetList();
        const currentSetId = window.sets.getCurrentSetId();

        container.innerHTML = '';

        setList.forEach((set, index) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'set-btn' + (set.id === currentSetId ? ' active' : '');
            btn.dataset.setId = set.id;
            btn.title = `${set.name} (${set.tubercleCount} tub, ${set.edgeCount} itc)` +
                        (index < 9 ? ` - Ctrl+${index + 1}` : '');

            // Truncate long names
            let displayName = set.name;
            if (displayName.length > 15) {
                displayName = displayName.substring(0, 14) + '…';
            }

            btn.innerHTML = displayName +
                (set.isDirty ? '<span class="dirty-indicator">*</span>' : '');

            btn.addEventListener('click', () => handleSetClick(set.id));
            container.appendChild(btn);
        });

        // Update add button state
        const addBtn = document.getElementById('addSetBtn');
        if (addBtn) {
            addBtn.disabled = !window.sets.canCreateMore();
        }

        // Update save button state
        updateSaveButton();
    }

    /**
     * Handle click on a set button
     */
    function handleSetClick(setId) {
        const currentSetId = window.sets.getCurrentSetId();
        if (setId === currentSetId) return;

        // Check for unsaved changes
        if (window.sets.hasUnsavedChanges()) {
            showUnsavedChangesDialog(() => {
                // Save and switch
                saveAndSwitch(setId);
            }, () => {
                // Switch without saving
                switchToSet(setId);
            });
        } else {
            switchToSet(setId);
        }
    }

    /**
     * Switch to a different set
     */
    function switchToSet(setId) {
        // Clear selection before switching
        window.overlay?.deselect();

        // Switch set
        window.sets.switchSet(setId);
    }

    /**
     * Save and then switch to another set
     */
    async function saveAndSwitch(setId) {
        const saved = await window.extraction?.saveSlo();
        if (saved) {
            window.sets.markAllClean();
            switchToSet(setId);
        }
    }

    /**
     * Show unsaved changes warning dialog
     */
    function showUnsavedChangesDialog(onSaveAndSwitch, onSwitch) {
        const currentSet = window.sets.getCurrentSet();
        const name = currentSet ? currentSet.name : 'current set';

        window.app.showModal(
            'Unsaved Changes',
            `<p>Set "${name}" has unsaved changes. What would you like to do?</p>`,
            [
                { text: 'Cancel', action: () => {} },
                { text: 'Switch Without Saving', action: onSwitch },
                { text: 'Save & Switch', primary: true, action: onSaveAndSwitch },
            ]
        );
    }

    /**
     * Handle add set button click
     */
    function handleAddSet() {
        showCreateSetDialog();
    }

    /**
     * Show create new set dialog
     */
    function showCreateSetDialog() {
        const html = `
            <p>Enter a name for the new set:</p>
            <input type="text" id="newSetName" class="modal-input" placeholder="Set name" maxlength="20" autofocus>
            <p style="margin-bottom: 0.5rem;">Initial contents:</p>
            <div class="modal-radio-group">
                <label class="modal-radio-label">
                    <input type="radio" name="setContent" value="empty" checked>
                    Empty (start fresh)
                </label>
                <label class="modal-radio-label">
                    <input type="radio" name="setContent" value="copy">
                    Copy from current set
                </label>
                <label class="modal-radio-label">
                    <input type="radio" name="setContent" value="extract">
                    Run extraction with current params
                </label>
            </div>
        `;

        window.app.showModal(
            'Create New Set',
            html,
            [
                { text: 'Cancel', action: () => {} },
                { text: 'Create', primary: true, action: createSetFromDialog },
            ]
        );

        // Focus input after modal is shown
        setTimeout(() => {
            const input = document.getElementById('newSetName');
            if (input) input.focus();
        }, 100);
    }

    /**
     * Create set from dialog inputs
     */
    async function createSetFromDialog() {
        const nameInput = document.getElementById('newSetName');
        const contentRadio = document.querySelector('input[name="setContent"]:checked');

        const name = nameInput?.value || 'New Set';
        const content = contentRadio?.value || 'empty';

        let options = {};

        if (content === 'copy') {
            const currentData = window.sets.getCurrentData();
            options = {
                tubercles: currentData.tubercles,
                edges: currentData.edges,
            };
        }

        const newSet = window.sets.createSet(name, options);
        if (!newSet) {
            window.app.showToast('Maximum number of sets reached', 'warning');
            return;
        }

        // Switch to the new set
        window.sets.switchSet(newSet.id);

        // If extraction requested, run it
        if (content === 'extract') {
            window.extraction?.runExtraction();
        }

        window.app.showToast(`Created set "${newSet.name}"`, 'success');
    }

    /**
     * Handle rename set button click
     */
    function handleRenameSet() {
        closeMenu();
        const currentSet = window.sets.getCurrentSet();
        if (!currentSet) return;

        const html = `
            <p>Current name: <strong>${currentSet.name}</strong></p>
            <input type="text" id="renameSetInput" class="modal-input"
                   placeholder="New name" maxlength="20" value="${currentSet.name}" autofocus>
        `;

        window.app.showModal(
            'Rename Set',
            html,
            [
                { text: 'Cancel', action: () => {} },
                { text: 'Rename', primary: true, action: () => {
                    const input = document.getElementById('renameSetInput');
                    const newName = input?.value?.trim();
                    if (newName && newName !== currentSet.name) {
                        if (window.sets.renameSet(currentSet.id, newName)) {
                            window.app.showToast(`Renamed to "${newName}"`, 'success');
                        } else {
                            window.app.showToast('Name already exists', 'warning');
                        }
                    }
                }},
            ]
        );

        setTimeout(() => {
            const input = document.getElementById('renameSetInput');
            if (input) {
                input.focus();
                input.select();
            }
        }, 100);
    }

    /**
     * Handle duplicate set button click
     */
    function handleDuplicateSet() {
        closeMenu();
        const currentSet = window.sets.getCurrentSet();
        if (!currentSet) return;

        const html = `
            <p>Duplicating: <strong>${currentSet.name}</strong></p>
            <input type="text" id="duplicateSetInput" class="modal-input"
                   placeholder="Name for duplicate" maxlength="20"
                   value="${currentSet.name} Copy" autofocus>
        `;

        window.app.showModal(
            'Duplicate Set',
            html,
            [
                { text: 'Cancel', action: () => {} },
                { text: 'Duplicate', primary: true, action: () => {
                    const input = document.getElementById('duplicateSetInput');
                    const name = input?.value?.trim() || (currentSet.name + ' Copy');
                    const newSet = window.sets.duplicateSet(currentSet.id, name);
                    if (newSet) {
                        window.sets.switchSet(newSet.id);
                        window.app.showToast(`Created "${newSet.name}"`, 'success');
                    } else {
                        window.app.showToast('Could not duplicate set', 'error');
                    }
                }},
            ]
        );

        setTimeout(() => {
            const input = document.getElementById('duplicateSetInput');
            if (input) {
                input.focus();
                input.select();
            }
        }, 100);
    }

    /**
     * Handle delete set button click
     */
    function handleDeleteSet() {
        closeMenu();
        const currentSet = window.sets.getCurrentSet();
        if (!currentSet) return;

        if (window.sets.getSetCount() <= 1) {
            window.app.showToast('Cannot delete the last set', 'warning');
            return;
        }

        window.app.showModal(
            'Delete Set',
            `<p>Are you sure you want to delete set "<strong>${currentSet.name}</strong>"?</p>
             <p style="color: var(--error-color); font-size: 0.85rem;">
                This will delete ${currentSet.tubercles.length} tubercles and
                ${currentSet.edges.length} connections.
             </p>`,
            [
                { text: 'Cancel', action: () => {} },
                { text: 'Delete', primary: true, action: () => {
                    window.sets.deleteSet(currentSet.id);
                    window.app.showToast(`Deleted set "${currentSet.name}"`, 'success');
                }},
            ]
        );
    }

    /**
     * Toggle the management menu
     */
    function toggleMenu() {
        menuOpen = !menuOpen;
        const dropdown = document.getElementById('setMenuDropdown');
        if (dropdown) {
            dropdown.style.display = menuOpen ? 'block' : 'none';
        }
    }

    /**
     * Close the management menu
     */
    function closeMenu() {
        menuOpen = false;
        const dropdown = document.getElementById('setMenuDropdown');
        if (dropdown) {
            dropdown.style.display = 'none';
        }
    }

    /**
     * Update the save button state
     */
    function updateSaveButton() {
        const saveBtn = document.getElementById('saveSetBtn');
        if (saveBtn) {
            saveBtn.disabled = !window.sets.anyUnsavedChanges();
        }
    }

    /**
     * Update the stats bar set name
     */
    function updateStatsBarSetName() {
        const el = document.getElementById('statsBarSetName');
        if (!el) return;

        const currentSet = window.sets.getCurrentSet();
        if (currentSet) {
            el.innerHTML = currentSet.name +
                (currentSet.isDirty ? '<span class="dirty-indicator">*</span>' : '');
        } else {
            el.textContent = 'No Set';
        }
    }

    /**
     * Bind button handlers
     */
    function bindHandlers() {
        // Add set button
        const addBtn = document.getElementById('addSetBtn');
        if (addBtn) {
            addBtn.addEventListener('click', handleAddSet);
        }

        // Save button
        const saveBtn = document.getElementById('saveSetBtn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                window.extraction?.saveSlo().then(saved => {
                    if (saved) {
                        window.sets.markAllClean();
                    }
                });
            });
        }

        // Shortcuts help button
        const shortcutsBtn = document.getElementById('shortcutsHelpBtn');
        if (shortcutsBtn) {
            shortcutsBtn.addEventListener('click', () => {
                window.open('/static/help/shortcuts.html', 'shortcuts', 'width=800,height=700');
            });
        }

        // Menu button
        const menuBtn = document.getElementById('setMenuBtn');
        if (menuBtn) {
            menuBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleMenu();
            });
        }

        // Menu items
        const renameBtn = document.getElementById('renameSetBtn');
        if (renameBtn) {
            renameBtn.addEventListener('click', handleRenameSet);
        }

        const duplicateBtn = document.getElementById('duplicateSetBtn');
        if (duplicateBtn) {
            duplicateBtn.addEventListener('click', handleDuplicateSet);
        }

        const deleteBtn = document.getElementById('deleteSetBtn');
        if (deleteBtn) {
            deleteBtn.addEventListener('click', handleDeleteSet);
        }

        // Close menu on click outside
        document.addEventListener('click', (e) => {
            if (menuOpen) {
                const container = document.querySelector('.set-menu-container');
                if (container && !container.contains(e.target)) {
                    closeMenu();
                }
            }
        });
    }

    /**
     * Bind set events
     */
    function bindSetEvents() {
        // Set created
        document.addEventListener('setCreated', () => {
            renderSetButtons();
        });

        // Set deleted
        document.addEventListener('setDeleted', () => {
            renderSetButtons();
        });

        // Set renamed
        document.addEventListener('setRenamed', () => {
            renderSetButtons();
            updateStatsBarSetName();
        });

        // Set changed (switched)
        document.addEventListener('setChanged', (e) => {
            renderSetButtons();
            updateStatsBarSetName();

            // Update other modules with new set data
            const set = e.detail.set;
            if (set) {
                window.overlay?.setData(set.tubercles, set.edges);
                window.editor?.setData(set.tubercles, set.edges);

                // Recalculate and display statistics
                const stats = calculateStatistics(set.tubercles, set.edges);
                window.data?.setData(set.tubercles, set.edges, stats);
            }
        });

        // Dirty state changed
        document.addEventListener('setDirtyStateChanged', () => {
            renderSetButtons();
            updateStatsBarSetName();
            updateSaveButton();
        });

        // Sets loaded from file
        document.addEventListener('setsLoaded', () => {
            renderSetButtons();
            updateStatsBarSetName();

            // Update displays with current set data
            const set = window.sets.getCurrentSet();
            if (set) {
                window.overlay?.setData(set.tubercles, set.edges);
                window.editor?.setData(set.tubercles, set.edges);

                const stats = calculateStatistics(set.tubercles, set.edges);
                window.data?.setData(set.tubercles, set.edges, stats);
            }
        });
    }

    /**
     * Calculate statistics from data
     */
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

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        renderSetButtons,
        updateSaveButton,
        updateStatsBarSetName,
    };
})();
