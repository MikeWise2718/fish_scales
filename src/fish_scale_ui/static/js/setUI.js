/**
 * Fish Scale Measurement UI - Set Selector UI
 * Handles the UI for multiple annotation sets
 */

window.setUI = (function() {
    let menuOpen = false;
    let statsBarMenuOpen = false;
    let dataTabMenuOpen = false;
    let extractionTabMenuOpen = false;

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

        // Update all set indicators
        updateAllSetIndicators();
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

        // Update add button state (in stats bar)
        const addBtn = document.getElementById('statsBarNewSetBtn');
        if (addBtn) {
            addBtn.disabled = !window.sets.canCreateMore();
        }

        // Update save button state
        updateSaveButton();
    }

    /**
     * Handle click on a set button
     * Note: No warning dialog needed - all set data is preserved in memory.
     * The dirty indicator (*) shows which sets need saving to disk.
     */
    function handleSetClick(setId) {
        const currentSetId = window.sets.getCurrentSetId();
        if (setId === currentSetId) return;

        switchToSet(setId);
    }

    /**
     * Navigate to the previous set
     */
    function handlePrevSet() {
        const setList = window.sets.getSetList();
        if (setList.length <= 1) return;

        const currentSetId = window.sets.getCurrentSetId();
        const currentIndex = setList.findIndex(s => s.id === currentSetId);
        if (currentIndex <= 0) return;

        const prevSetId = setList[currentIndex - 1].id;
        handleSetClick(prevSetId);
    }

    /**
     * Navigate to the next set
     */
    function handleNextSet() {
        const setList = window.sets.getSetList();
        if (setList.length <= 1) return;

        const currentSetId = window.sets.getCurrentSetId();
        const currentIndex = setList.findIndex(s => s.id === currentSetId);
        if (currentIndex >= setList.length - 1) return;

        const nextSetId = setList[currentIndex + 1].id;
        handleSetClick(nextSetId);
    }

    /**
     * Update the prev/next navigation buttons' disabled state
     */
    function updateSetNavButtons() {
        const prevBtn = document.getElementById('prevSetBtn');
        const nextBtn = document.getElementById('nextSetBtn');
        if (!prevBtn || !nextBtn) return;

        const setList = window.sets.getSetList();
        const currentSetId = window.sets.getCurrentSetId();
        const currentIndex = setList.findIndex(s => s.id === currentSetId);

        prevBtn.disabled = currentIndex <= 0 || setList.length <= 1;
        nextBtn.disabled = currentIndex >= setList.length - 1 || setList.length <= 1;
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
        const setList = window.sets.getSetList();
        const currentSetId = window.sets.getCurrentSetId();

        // Build options for the copy-from dropdown
        let copyFromOptions = setList.map(set => {
            const selected = set.id === currentSetId ? ' selected' : '';
            return `<option value="${set.id}"${selected}>${set.name}</option>`;
        }).join('');

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
                    Copy from:
                    <select id="copyFromSetSelect" class="modal-select" style="margin-left: 0.5rem; padding: 0.25rem; font-size: 0.85rem;">
                        ${copyFromOptions}
                    </select>
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
        const copyFromSelect = document.getElementById('copyFromSetSelect');

        const name = nameInput?.value || 'New Set';
        const content = contentRadio?.value || 'empty';

        let options = {};

        if (content === 'copy' && copyFromSelect) {
            const sourceSetId = copyFromSelect.value;
            const sourceSet = window.sets.getSet(sourceSetId);
            if (sourceSet) {
                options = {
                    tubercles: JSON.parse(JSON.stringify(sourceSet.tubercles)),
                    edges: JSON.parse(JSON.stringify(sourceSet.edges)),
                    parameters: sourceSet.parameters ? { ...sourceSet.parameters } : undefined,
                };
            }
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
     * Save is always enabled - overwrite protection is handled by the save dialog
     */
    function updateSaveButton() {
        // Save buttons are always enabled
        // Overwrite protection with comparison dialog is shown when saving
        const saveBtn = document.getElementById('saveSetBtn');
        if (saveBtn) {
            saveBtn.disabled = false;
        }
        const saveAsBtn = document.getElementById('saveAsBtn');
        if (saveAsBtn) {
            saveAsBtn.disabled = false;
        }
    }

    /**
     * Update all set indicators across the UI
     */
    function updateAllSetIndicators() {
        updateStatsBarSetName();
        updateDataTabSetName();
        updateEditTabSetName();
        updateExtractionTabSetName();
        updateSetNavButtons();
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
     * Update the Data tab set name
     */
    function updateDataTabSetName() {
        const el = document.getElementById('dataTabSetName');
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
     * Update the Edit tab set name
     */
    function updateEditTabSetName() {
        const el = document.getElementById('editTabSetName');
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
     * Update the Extraction tab set name
     */
    function updateExtractionTabSetName() {
        const el = document.getElementById('extractionTabSetName');
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
     * Close all dropdown menus
     */
    function closeAllMenus() {
        closeMenu();
        closeStatsBarMenu();
        closeDataTabMenu();
        closeExtractionTabMenu();
    }

    /**
     * Toggle the stats bar set menu
     */
    function toggleStatsBarMenu() {
        statsBarMenuOpen = !statsBarMenuOpen;
        if (statsBarMenuOpen) {
            renderStatsBarMenu();
            closeMenu();
            closeDataTabMenu();
        }
        const menu = document.getElementById('statsBarSetMenu');
        if (menu) {
            menu.style.display = statsBarMenuOpen ? 'block' : 'none';
        }
    }

    /**
     * Close the stats bar set menu
     */
    function closeStatsBarMenu() {
        statsBarMenuOpen = false;
        const menu = document.getElementById('statsBarSetMenu');
        if (menu) {
            menu.style.display = 'none';
        }
    }

    /**
     * Render the stats bar set menu
     */
    function renderStatsBarMenu() {
        const menu = document.getElementById('statsBarSetMenu');
        if (!menu) return;

        const setList = window.sets.getSetList();
        const currentSetId = window.sets.getCurrentSetId();

        let html = '';

        // Set list
        setList.forEach(set => {
            const isActive = set.id === currentSetId;
            html += `
                <button class="stats-bar-set-menu-item${isActive ? ' active' : ''}"
                        data-set-id="${set.id}">
                    ${set.name}${set.isDirty ? '<span class="dirty-indicator">*</span>' : ''}
                </button>
            `;
        });

        // Divider and actions
        html += `
            <hr class="stats-bar-set-menu-divider">
            <button class="stats-bar-set-menu-action" id="statsBarManageSetsBtn">
                Manage Sets...
            </button>
        `;

        menu.innerHTML = html;

        // Bind click handlers
        menu.querySelectorAll('.stats-bar-set-menu-item').forEach(item => {
            item.addEventListener('click', () => {
                const setId = item.dataset.setId;
                closeStatsBarMenu();
                handleSetClick(setId);
            });
        });

        const manageSetsBtn = document.getElementById('statsBarManageSetsBtn');
        if (manageSetsBtn) {
            manageSetsBtn.addEventListener('click', () => {
                closeStatsBarMenu();
                // Switch to Extraction tab and scroll to set selector
                const extractionTab = document.querySelector('.tab-header[data-tab="extraction"]');
                if (extractionTab) {
                    extractionTab.click();
                }
            });
        }
    }

    /**
     * Toggle the Data tab set menu
     */
    function toggleDataTabMenu() {
        dataTabMenuOpen = !dataTabMenuOpen;
        if (dataTabMenuOpen) {
            renderDataTabMenu();
            closeMenu();
            closeStatsBarMenu();
        }
        const menu = document.getElementById('dataTabSetMenu');
        if (menu) {
            menu.style.display = dataTabMenuOpen ? 'block' : 'none';
        }
    }

    /**
     * Close the Data tab set menu
     */
    function closeDataTabMenu() {
        dataTabMenuOpen = false;
        const menu = document.getElementById('dataTabSetMenu');
        if (menu) {
            menu.style.display = 'none';
        }
    }

    /**
     * Render the Data tab set menu
     */
    function renderDataTabMenu() {
        const menu = document.getElementById('dataTabSetMenu');
        if (!menu) return;

        const setList = window.sets.getSetList();
        const currentSetId = window.sets.getCurrentSetId();

        let html = '';

        // Set list
        setList.forEach(set => {
            const isActive = set.id === currentSetId;
            html += `
                <button class="tab-set-menu-item${isActive ? ' active' : ''}"
                        data-set-id="${set.id}">
                    ${set.name}${set.isDirty ? '<span class="dirty-indicator">*</span>' : ''}
                </button>
            `;
        });

        menu.innerHTML = html;

        // Bind click handlers
        menu.querySelectorAll('.tab-set-menu-item').forEach(item => {
            item.addEventListener('click', () => {
                const setId = item.dataset.setId;
                closeDataTabMenu();
                handleSetClick(setId);
            });
        });
    }

    /**
     * Toggle the Extraction tab set menu
     */
    function toggleExtractionTabMenu() {
        extractionTabMenuOpen = !extractionTabMenuOpen;
        if (extractionTabMenuOpen) {
            renderExtractionTabMenu();
            closeMenu();
            closeStatsBarMenu();
            closeDataTabMenu();
        }
        const menu = document.getElementById('extractionTabSetMenu');
        if (menu) {
            menu.style.display = extractionTabMenuOpen ? 'block' : 'none';
        }
    }

    /**
     * Close the Extraction tab set menu
     */
    function closeExtractionTabMenu() {
        extractionTabMenuOpen = false;
        const menu = document.getElementById('extractionTabSetMenu');
        if (menu) {
            menu.style.display = 'none';
        }
    }

    /**
     * Render the Extraction tab set menu
     */
    function renderExtractionTabMenu() {
        const menu = document.getElementById('extractionTabSetMenu');
        if (!menu) return;

        const setList = window.sets.getSetList();
        const currentSetId = window.sets.getCurrentSetId();

        let html = '';

        // Set list
        setList.forEach(set => {
            const isActive = set.id === currentSetId;
            html += `
                <button class="tab-set-menu-item${isActive ? ' active' : ''}"
                        data-set-id="${set.id}">
                    ${set.name}${set.isDirty ? '<span class="dirty-indicator">*</span>' : ''}
                </button>
            `;
        });

        menu.innerHTML = html;

        // Bind click handlers
        menu.querySelectorAll('.tab-set-menu-item').forEach(item => {
            item.addEventListener('click', () => {
                const setId = item.dataset.setId;
                closeExtractionTabMenu();
                handleSetClick(setId);
            });
        });
    }

    /**
     * Bind button handlers
     */
    function bindHandlers() {
        // Add set button (stats bar)
        const addBtn = document.getElementById('statsBarNewSetBtn');
        if (addBtn) {
            addBtn.addEventListener('click', handleAddSet);
        }

        // Prev/Next set navigation buttons
        const prevBtn = document.getElementById('prevSetBtn');
        if (prevBtn) {
            prevBtn.addEventListener('click', handlePrevSet);
        }
        const nextBtn = document.getElementById('nextSetBtn');
        if (nextBtn) {
            nextBtn.addEventListener('click', handleNextSet);
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

        // Save As button
        const saveAsBtn = document.getElementById('saveAsBtn');
        if (saveAsBtn) {
            saveAsBtn.addEventListener('click', () => {
                window.extraction?.saveSloAs();
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
                const container = document.querySelector('.stats-bar-gear-container');
                if (container && !container.contains(e.target)) {
                    closeMenu();
                }
            }
            if (statsBarMenuOpen) {
                const container = document.getElementById('statsBarSetDropdown');
                if (container && !container.contains(e.target)) {
                    closeStatsBarMenu();
                }
            }
            if (dataTabMenuOpen) {
                const container = document.getElementById('dataTabSetDropdown');
                if (container && !container.contains(e.target)) {
                    closeDataTabMenu();
                }
            }
            if (extractionTabMenuOpen) {
                const container = document.getElementById('extractionTabSetDropdown');
                if (container && !container.contains(e.target)) {
                    closeExtractionTabMenu();
                }
            }
        });

        // Stats bar set dropdown button
        const statsBarSetBtn = document.getElementById('statsBarSetBtn');
        if (statsBarSetBtn) {
            statsBarSetBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleStatsBarMenu();
            });
        }

        // Stats bar "+ New" button
        const statsBarNewSetBtn = document.getElementById('statsBarNewSetBtn');
        if (statsBarNewSetBtn) {
            statsBarNewSetBtn.addEventListener('click', () => {
                showCreateSetDialog();
            });
        }

        // Data tab set dropdown button
        const dataTabSetBtn = document.getElementById('dataTabSetBtn');
        if (dataTabSetBtn) {
            dataTabSetBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleDataTabMenu();
            });
        }

        // Data tab "+ New Set" button
        const dataTabNewSetBtn = document.getElementById('dataTabNewSetBtn');
        if (dataTabNewSetBtn) {
            dataTabNewSetBtn.addEventListener('click', () => {
                showCreateSetDialog();
            });
        }

        // Extraction tab set dropdown button
        const extractionTabSetBtn = document.getElementById('extractionTabSetBtn');
        if (extractionTabSetBtn) {
            extractionTabSetBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleExtractionTabMenu();
            });
        }

        // Extraction tab "+ New Set" button
        const extractionTabNewSetBtn = document.getElementById('extractionTabNewSetBtn');
        if (extractionTabNewSetBtn) {
            extractionTabNewSetBtn.addEventListener('click', () => {
                showCreateSetDialog();
            });
        }

        // Edit tab "+ New Set" button
        const editTabNewSetBtn = document.getElementById('editTabNewSetBtn');
        if (editTabNewSetBtn) {
            editTabNewSetBtn.addEventListener('click', () => {
                showCreateSetDialog();
            });
        }
    }

    /**
     * Bind set events
     */
    function bindSetEvents() {
        // Set created
        document.addEventListener('setCreated', () => {
            renderSetButtons();
            updateAllSetIndicators();
        });

        // Set deleted
        document.addEventListener('setDeleted', () => {
            renderSetButtons();
            updateAllSetIndicators();
        });

        // Set renamed
        document.addEventListener('setRenamed', () => {
            renderSetButtons();
            updateAllSetIndicators();
        });

        // Set changed (switched)
        document.addEventListener('setChanged', (e) => {
            renderSetButtons();
            updateAllSetIndicators();
            closeAllMenus();

            // Update other modules with new set data
            const set = e.detail.set;
            if (set) {
                window.overlay?.setData(set.tubercles, set.edges);
                window.editor?.setData(set.tubercles, set.edges);

                // Recalculate and display statistics (async)
                calculateStatistics(set.tubercles, set.edges).then(stats => {
                    window.data?.setData(set.tubercles, set.edges, stats);
                });

                // Sync parameters to Configure tab if set has stored parameters
                if (set.parameters && window.configure?.setParams) {
                    window.configure.setParams(set.parameters);
                }
            }
        });

        // Dirty state changed
        document.addEventListener('setDirtyStateChanged', () => {
            renderSetButtons();
            updateAllSetIndicators();
            updateSaveButton();
        });

        // Data changed (extraction completed, data edited, etc.)
        document.addEventListener('setDataChanged', () => {
            updateSaveButton();
        });

        // Sets loaded from file
        document.addEventListener('setsLoaded', () => {
            renderSetButtons();
            updateAllSetIndicators();

            // Update displays with current set data
            const set = window.sets.getCurrentSet();
            if (set) {
                window.overlay?.setData(set.tubercles, set.edges);
                window.editor?.setData(set.tubercles, set.edges);

                // Async stats calculation
                calculateStatistics(set.tubercles, set.edges).then(stats => {
                    window.data?.setData(set.tubercles, set.edges, stats);
                });

                // Sync parameters to Configure tab if set has stored parameters
                if (set.parameters && window.configure?.setParams) {
                    window.configure.setParams(set.parameters);
                }
            }
        });

        // Hexagonalness weights changed - recalculate statistics
        window.addEventListener('hexWeightsChanged', () => {
            const set = window.sets?.getCurrentSet();
            if (set) {
                calculateStatistics(set.tubercles, set.edges).then(stats => {
                    window.data?.setData(set.tubercles, set.edges, stats);
                });
            }
        });
    }

    /**
     * Calculate statistics from data (async - fetches hexagonalness from server)
     */
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
        const hexMetrics = await fetchHexagonalness();

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

    /**
     * Fetch hexagonalness metrics from server API
     */
    async function fetchHexagonalness() {
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

            // Get current data from overlay (ensures fresh calculation)
            const tubercles = window.overlay?.getTubercles() || [];
            const edges = window.overlay?.getEdges() || [];

            const response = await fetch('/api/hexagonalness', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    spacing_weight: spacingWeight,
                    degree_weight: degreeWeight,
                    edge_ratio_weight: edgeRatioWeight,
                    tubercles: tubercles,
                    edges: edges,
                }),
            });
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

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        renderSetButtons,
        updateSaveButton,
        updateStatsBarSetName,
        updateDataTabSetName,
        updateEditTabSetName,
        updateExtractionTabSetName,
        updateAllSetIndicators,
        showCreateSetDialog,
    };
})();
