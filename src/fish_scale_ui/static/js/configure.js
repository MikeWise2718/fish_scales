/**
 * Fish Scale Measurement UI - Configure Tab
 */

window.configure = (function() {
    const STORAGE_KEY = 'fishScaleParams';
    const USER_PROFILES_KEY = 'fishScaleUserProfiles';
    const MAX_UNDO_HISTORY = 20;

    // Default parameter values
    const defaults = {
        method: 'log',
        threshold: 0.05,
        min_diameter_um: 2.0,
        max_diameter_um: 10.0,
        min_circularity: 0.5,
        clahe_clip: 0.03,
        clahe_kernel: 8,
        blur_sigma: 1.0,
        neighbor_graph: 'delaunay',
        cull_long_edges: true,
        cull_factor: 1.8,
    };

    // Current values (for change detection)
    let currentParams = { ...defaults };
    let lastExtractedParams = null;

    // Undo history stack
    let undoHistory = [];
    let isApplyingUndo = false;

    // Built-in profiles (from server)
    let builtInProfiles = [];

    // ==================== Persistence ====================

    // Save parameters to localStorage
    function saveToStorage() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(currentParams));
        } catch (err) {
            console.warn('Failed to save params to localStorage:', err);
        }
    }

    // Load parameters from localStorage
    function loadFromStorage() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                return JSON.parse(stored);
            }
        } catch (err) {
            console.warn('Failed to load params from localStorage:', err);
        }
        return null;
    }

    // Apply parameters to form inputs
    function applyParamsToForm(params) {
        if (!params) return;

        for (const [id, value] of Object.entries(params)) {
            const input = document.getElementById(id);
            if (input && value !== undefined && value !== null) {
                if (input.type === 'checkbox') {
                    input.checked = value;
                } else {
                    input.value = value;
                }
                // Update range display if exists
                updateValueDisplay(id, value);
            }
        }
        updateCullFactorVisibility();
    }

    // Update a value display element (span or input)
    function updateValueDisplay(id, value) {
        const display = document.getElementById(`${id}_value`);
        if (display) {
            const val = parseFloat(value);
            const formatted = isNaN(val) ? value : val.toFixed(3);
            if (display.tagName === 'INPUT') {
                display.value = formatted;
            } else {
                display.textContent = formatted;
            }
        }
    }

    // ==================== Undo System ====================

    // Push current state to undo history
    function pushUndo() {
        if (isApplyingUndo) return;

        undoHistory.push({ ...currentParams });
        if (undoHistory.length > MAX_UNDO_HISTORY) {
            undoHistory.shift();
        }
        updateUndoButton();
    }

    // Undo last parameter change
    function undo() {
        if (undoHistory.length === 0) return;

        isApplyingUndo = true;
        const prevState = undoHistory.pop();
        applyParamsToForm(prevState);
        currentParams = { ...prevState };
        saveToStorage();
        checkParamsChanged();
        updateUndoButton();
        isApplyingUndo = false;
    }

    // Update undo button state
    function updateUndoButton() {
        const btn = document.getElementById('undoParamsBtn');
        if (btn) {
            btn.disabled = undoHistory.length === 0;
            btn.title = undoHistory.length > 0
                ? `Undo (${undoHistory.length} step${undoHistory.length > 1 ? 's' : ''} available)`
                : 'No undo history';
        }
    }

    // ==================== Profiles ====================

    // Load built-in profiles from server
    async function loadBuiltInProfiles() {
        try {
            const response = await fetch('/api/profiles');
            const data = await response.json();
            if (data.profiles) {
                builtInProfiles = data.profiles;
            }
        } catch (err) {
            console.error('Failed to load built-in profiles:', err);
        }
    }

    // Get user-defined profiles from localStorage
    function getUserProfiles() {
        try {
            const stored = localStorage.getItem(USER_PROFILES_KEY);
            if (stored) {
                return JSON.parse(stored);
            }
        } catch (err) {
            console.warn('Failed to load user profiles:', err);
        }
        return [];
    }

    // Save user-defined profiles to localStorage
    function saveUserProfiles(profiles) {
        try {
            localStorage.setItem(USER_PROFILES_KEY, JSON.stringify(profiles));
        } catch (err) {
            console.warn('Failed to save user profiles:', err);
        }
    }

    // Render the profile select dropdown
    function renderProfileSelect() {
        const select = document.getElementById('profileSelect');
        if (!select) return;

        select.innerHTML = '<option value="">-- Select Profile --</option>';

        // Add built-in profiles
        if (builtInProfiles.length > 0) {
            const builtInGroup = document.createElement('optgroup');
            builtInGroup.label = 'Built-in Profiles';
            builtInProfiles.forEach(profile => {
                const option = document.createElement('option');
                option.value = `builtin:${profile.name}`;
                option.textContent = `${profile.name} - ${profile.description}`;
                option.dataset.profile = JSON.stringify(profile);
                option.dataset.builtin = 'true';
                builtInGroup.appendChild(option);
            });
            select.appendChild(builtInGroup);
        }

        // Add user profiles
        const userProfiles = getUserProfiles();
        if (userProfiles.length > 0) {
            const userGroup = document.createElement('optgroup');
            userGroup.label = 'User Profiles';
            userProfiles.forEach(profile => {
                const option = document.createElement('option');
                option.value = `user:${profile.name}`;
                option.textContent = profile.name;
                option.dataset.profile = JSON.stringify(profile);
                option.dataset.builtin = 'false';
                userGroup.appendChild(option);
            });
            select.appendChild(userGroup);
        }
    }

    // Render the profile list in the management container
    function renderProfileList() {
        const container = document.getElementById('profileListContainer');
        if (!container) return;

        const userProfiles = getUserProfiles();

        if (userProfiles.length === 0) {
            container.innerHTML = '<p class="empty-profiles">No user profiles saved yet.</p>';
            return;
        }

        let html = '<ul class="profile-list">';
        userProfiles.forEach((profile, idx) => {
            html += `
                <li class="profile-item">
                    <span class="profile-name">${escapeHtml(profile.name)}</span>
                    <button class="btn-icon btn-delete-profile" data-index="${idx}" title="Delete profile">
                        <span class="icon-delete">✕</span>
                    </button>
                </li>
            `;
        });
        html += '</ul>';
        container.innerHTML = html;

        // Add delete handlers
        container.querySelectorAll('.btn-delete-profile').forEach(btn => {
            btn.addEventListener('click', () => {
                const idx = parseInt(btn.dataset.index);
                deleteUserProfile(idx);
            });
        });
    }

    // Save current parameters as a new user profile
    function saveAsNewProfile() {
        const nameInput = document.getElementById('newProfileName');
        if (!nameInput) return;

        const name = nameInput.value.trim();
        if (!name) {
            alert('Please enter a profile name.');
            return;
        }

        // Check for duplicate names
        const userProfiles = getUserProfiles();
        const builtInNames = builtInProfiles.map(p => p.name.toLowerCase());
        const userNames = userProfiles.map(p => p.name.toLowerCase());

        if (builtInNames.includes(name.toLowerCase())) {
            alert('Cannot use a built-in profile name.');
            return;
        }

        if (userNames.includes(name.toLowerCase())) {
            if (!confirm(`Profile "${name}" already exists. Overwrite?`)) {
                return;
            }
            // Remove existing
            const existingIdx = userProfiles.findIndex(p => p.name.toLowerCase() === name.toLowerCase());
            if (existingIdx >= 0) {
                userProfiles.splice(existingIdx, 1);
            }
        }

        // Create new profile from current params
        const newProfile = {
            name: name,
            ...currentParams,
        };

        userProfiles.push(newProfile);
        saveUserProfiles(userProfiles);

        // Refresh UI
        renderProfileSelect();
        renderProfileList();
        nameInput.value = '';

        // Show confirmation
        window.app?.showStatus?.(`Profile "${name}" saved.`, 'success');
    }

    // Delete a user profile by index
    function deleteUserProfile(index) {
        const userProfiles = getUserProfiles();
        if (index < 0 || index >= userProfiles.length) return;

        const profile = userProfiles[index];
        if (!confirm(`Delete profile "${profile.name}"?`)) {
            return;
        }

        userProfiles.splice(index, 1);
        saveUserProfiles(userProfiles);

        // Refresh UI
        renderProfileSelect();
        renderProfileList();

        window.app?.showStatus?.(`Profile "${profile.name}" deleted.`, 'info');
    }

    // Apply a profile to the form
    function applyProfile(profileData) {
        if (!profileData) return;

        // Push current state to undo before applying
        pushUndo();

        const fields = {
            'threshold': profileData.threshold,
            'min_diameter_um': profileData.min_diameter_um,
            'max_diameter_um': profileData.max_diameter_um,
            'min_circularity': profileData.min_circularity,
            'clahe_clip': profileData.clahe_clip,
            'clahe_kernel': profileData.clahe_kernel,
            'blur_sigma': profileData.blur_sigma,
        };

        for (const [id, value] of Object.entries(fields)) {
            const input = document.getElementById(id);
            if (input && value !== undefined && value !== null) {
                input.value = value;
                updateValueDisplay(id, value);
            }
        }

        // Update calibration if profile has it
        if (profileData.calibration_um_per_px && window.calibration) {
            const umPerPxInput = document.getElementById('umPerPx');
            if (umPerPxInput) {
                umPerPxInput.value = profileData.calibration_um_per_px;
            }
        }

        updateCurrentParams();
        saveToStorage();
        checkParamsChanged();
    }

    // ==================== Core Functions ====================

    // Get current parameters from form
    function getParams() {
        const cullCheckbox = document.getElementById('cull_long_edges');
        return {
            method: document.getElementById('method')?.value || defaults.method,
            threshold: parseFloat(document.getElementById('threshold')?.value) || defaults.threshold,
            min_diameter_um: parseFloat(document.getElementById('min_diameter_um')?.value) || defaults.min_diameter_um,
            max_diameter_um: parseFloat(document.getElementById('max_diameter_um')?.value) || defaults.max_diameter_um,
            min_circularity: parseFloat(document.getElementById('min_circularity')?.value) || defaults.min_circularity,
            clahe_clip: parseFloat(document.getElementById('clahe_clip')?.value) || defaults.clahe_clip,
            clahe_kernel: parseInt(document.getElementById('clahe_kernel')?.value) || defaults.clahe_kernel,
            blur_sigma: parseFloat(document.getElementById('blur_sigma')?.value) || defaults.blur_sigma,
            neighbor_graph: document.getElementById('neighbor_graph')?.value || defaults.neighbor_graph,
            cull_long_edges: cullCheckbox ? cullCheckbox.checked : defaults.cull_long_edges,
            cull_factor: parseFloat(document.getElementById('cull_factor')?.value) || defaults.cull_factor,
        };
    }

    // Update current params from form
    function updateCurrentParams() {
        currentParams = getParams();
    }

    // Handle parameter change (with undo support)
    function onParamChange() {
        pushUndo();
        updateCurrentParams();
        saveToStorage();
        checkParamsChanged();
    }

    // Check if params changed since last extraction
    function checkParamsChanged() {
        if (!lastExtractedParams) {
            setParamsChanged(false);
            return;
        }

        const current = getParams();
        const changed = Object.keys(current).some(key =>
            current[key] !== lastExtractedParams[key]
        );
        setParamsChanged(changed);
    }

    // Set visual indicator for params changed
    function setParamsChanged(changed) {
        const indicator = document.getElementById('paramsChangedIndicator');
        if (indicator) {
            indicator.style.display = changed ? 'inline-block' : 'none';
        }
    }

    // Mark last extracted params
    function markExtracted(params) {
        lastExtractedParams = { ...params };
        setParamsChanged(false);
    }

    // Reset to defaults
    function resetToDefaults() {
        pushUndo();

        for (const [id, value] of Object.entries(defaults)) {
            const input = document.getElementById(id);
            if (input) {
                if (input.type === 'checkbox') {
                    input.checked = value;
                } else {
                    input.value = value;
                }
                updateValueDisplay(id, value);
            }
        }
        // Update cull factor row visibility
        updateCullFactorVisibility();
        updateCurrentParams();
        saveToStorage();
        checkParamsChanged();
    }

    /**
     * Set parameters programmatically from an external source.
     * Used by agent_extraction.js and data.js to sync parameters.
     * @param {Object} params - Parameter object with keys matching form input IDs
     */
    function setParams(params) {
        if (!params || typeof params !== 'object') return;

        pushUndo();

        // Merge with defaults to ensure all params have values
        const mergedParams = { ...defaults, ...params };

        // Apply to form controls
        applyParamsToForm(mergedParams);

        // Update internal state
        currentParams = { ...mergedParams };
        saveToStorage();
        checkParamsChanged();
    }

    /**
     * Apply parameters from history restoration.
     * Sets parameters, switches to Configure tab, and shows confirmation.
     * @param {Object} params - Parameter object to apply
     */
    function applyParameters(params) {
        if (!params || typeof params !== 'object') {
            window.app?.showToast('Invalid parameters', 'error');
            return;
        }

        // Set the parameters
        setParams(params);

        // Switch to Configure tab
        const configBtn = document.querySelector('[data-tab="configure"]');
        if (configBtn) {
            configBtn.click();
        }

        // Show confirmation toast
        window.app?.showToast('Parameters restored from history', 'success');
    }

    /**
     * Enable or disable all Configure tab controls.
     * Used during agent optimization to prevent manual interference.
     * @param {boolean} enabled - Whether controls should be enabled
     */
    function setEnabled(enabled) {
        // Parameter inputs (sliders, selects, checkboxes)
        const paramInputs = document.querySelectorAll('.param-input');
        paramInputs.forEach(input => {
            input.disabled = !enabled;
        });

        // Editable value inputs (number inputs next to sliders)
        const editableValues = document.querySelectorAll('.param-value-editable');
        editableValues.forEach(input => {
            input.disabled = !enabled;
        });

        // Profile select
        const profileSelect = document.getElementById('profileSelect');
        if (profileSelect) {
            profileSelect.disabled = !enabled;
        }

        // Buttons
        const buttons = [
            'resetParamsBtn',
            'undoParamsBtn',
            'saveProfileBtn',
        ];
        buttons.forEach(id => {
            const btn = document.getElementById(id);
            if (btn) {
                btn.disabled = !enabled;
            }
        });

        // Add/remove visual indicator class on the configure tab content
        const configureTab = document.getElementById('tab-configure');
        if (configureTab) {
            configureTab.classList.toggle('controls-disabled', !enabled);
        }
    }

    // Show/hide cull factor row based on checkbox
    function updateCullFactorVisibility() {
        const checkbox = document.getElementById('cull_long_edges');
        const row = document.getElementById('cullFactorRow');
        if (checkbox && row) {
            row.style.display = checkbox.checked ? 'flex' : 'none';
        }
    }

    // Escape HTML for safe insertion
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // ==================== Initialization ====================

    async function init() {
        // Load built-in profiles first
        await loadBuiltInProfiles();

        // Render profile select and list
        renderProfileSelect();
        renderProfileList();

        // Load saved params from localStorage
        const savedParams = loadFromStorage();
        if (savedParams) {
            applyParamsToForm(savedParams);
            currentParams = { ...savedParams };
        }

        // Profile select handler
        const profileSelect = document.getElementById('profileSelect');
        if (profileSelect) {
            profileSelect.addEventListener('change', (e) => {
                const selected = e.target.selectedOptions[0];
                if (selected && selected.dataset.profile) {
                    const profile = JSON.parse(selected.dataset.profile);
                    applyProfile(profile);
                }
            });
        }

        // Add change listeners to all parameter inputs
        const paramInputs = document.querySelectorAll('.param-input');
        paramInputs.forEach(input => {
            input.addEventListener('change', onParamChange);
            input.addEventListener('input', () => {
                // Update range display for sliders
                updateValueDisplay(input.id, input.value);
            });
        });

        // Add bidirectional sync for editable value inputs
        const editableValues = document.querySelectorAll('.param-value-editable');
        editableValues.forEach(valueInput => {
            // Get the corresponding slider (id without _value suffix)
            const sliderId = valueInput.id.replace('_value', '');
            const slider = document.getElementById(sliderId);

            if (slider) {
                // Sync number input -> slider
                valueInput.addEventListener('input', () => {
                    const val = parseFloat(valueInput.value);
                    if (!isNaN(val)) {
                        // Clamp to slider range
                        const min = parseFloat(slider.min) || 0;
                        const max = parseFloat(slider.max) || 1;
                        slider.value = Math.max(min, Math.min(max, val));
                    }
                });
                valueInput.addEventListener('change', onParamChange);
            }
        });

        // Cull long edges checkbox handler
        const cullCheckbox = document.getElementById('cull_long_edges');
        if (cullCheckbox) {
            cullCheckbox.addEventListener('change', () => {
                updateCullFactorVisibility();
                onParamChange();
            });
            // Initialize visibility on load
            updateCullFactorVisibility();
        }

        // Reset button
        const resetBtn = document.getElementById('resetParamsBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', resetToDefaults);
        }

        // Undo button
        const undoBtn = document.getElementById('undoParamsBtn');
        if (undoBtn) {
            undoBtn.addEventListener('click', undo);
        }
        updateUndoButton();

        // Save profile button
        const saveProfileBtn = document.getElementById('saveProfileBtn');
        if (saveProfileBtn) {
            saveProfileBtn.addEventListener('click', saveAsNewProfile);
        }

        // Enter key in profile name input
        const nameInput = document.getElementById('newProfileName');
        if (nameInput) {
            nameInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    saveAsNewProfile();
                }
            });
        }

        // Profile presets collapsible toggle
        const profileToggle = document.getElementById('profilePresetsToggle');
        const profileContent = document.getElementById('profilePresetsContent');
        if (profileToggle && profileContent) {
            profileToggle.addEventListener('click', () => {
                const isOpen = profileContent.style.display !== 'none';
                profileContent.style.display = isOpen ? 'none' : 'block';
                profileToggle.classList.toggle('collapsed', isOpen);
            });
        }

        // Help icons for parameters (only those with data-param attribute)
        const helpIcons = document.querySelectorAll('.help-icon[data-param]');
        helpIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                e.preventDefault();
                const param = icon.dataset.param;
                window.open(`/static/help/parameters.html#${param}`, 'help', 'width=800,height=600');
            });
        });
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        getParams,
        setParams,
        applyParameters,  // v3.0: for history restoration
        setEnabled,
        markExtracted,
        checkParamsChanged,
        applyProfile,
        resetToDefaults,
        undo,
        defaults,
    };
})();
