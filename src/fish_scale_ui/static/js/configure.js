/**
 * Fish Scale Measurement UI - Configure Tab
 */

window.configure = (function() {
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

    // Load profiles from server
    async function loadProfiles() {
        try {
            const response = await fetch('/api/profiles');
            const data = await response.json();
            const select = document.getElementById('profileSelect');

            if (select && data.profiles) {
                select.innerHTML = '<option value="">-- Select Profile --</option>';
                data.profiles.forEach(profile => {
                    const option = document.createElement('option');
                    option.value = profile.name;
                    option.textContent = `${profile.name} - ${profile.description}`;
                    option.dataset.profile = JSON.stringify(profile);
                    select.appendChild(option);
                });
            }
        } catch (err) {
            console.error('Failed to load profiles:', err);
        }
    }

    // Apply a profile to the form
    function applyProfile(profileData) {
        if (!profileData) return;

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
                // Update range display if exists
                const display = document.getElementById(`${id}_value`);
                if (display) display.textContent = value;
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
        checkParamsChanged();
    }

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
        for (const [id, value] of Object.entries(defaults)) {
            const input = document.getElementById(id);
            if (input) {
                if (input.type === 'checkbox') {
                    input.checked = value;
                } else {
                    input.value = value;
                }
                const display = document.getElementById(`${id}_value`);
                if (display) display.textContent = value;
            }
        }
        // Update cull factor row visibility
        updateCullFactorVisibility();
        updateCurrentParams();
        checkParamsChanged();
    }

    // Show/hide cull factor row based on checkbox
    function updateCullFactorVisibility() {
        const checkbox = document.getElementById('cull_long_edges');
        const row = document.getElementById('cullFactorRow');
        if (checkbox && row) {
            row.style.display = checkbox.checked ? 'flex' : 'none';
        }
    }

    // Initialize
    function init() {
        // Load profiles
        loadProfiles();

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
            input.addEventListener('change', () => {
                updateCurrentParams();
                checkParamsChanged();
            });
            input.addEventListener('input', () => {
                // Update range display
                const display = document.getElementById(`${input.id}_value`);
                if (display) display.textContent = input.value;
            });
        });

        // Cull long edges checkbox handler
        const cullCheckbox = document.getElementById('cull_long_edges');
        if (cullCheckbox) {
            cullCheckbox.addEventListener('change', () => {
                updateCullFactorVisibility();
                updateCurrentParams();
                checkParamsChanged();
            });
            // Initialize visibility on load
            updateCullFactorVisibility();
        }

        // Reset button
        const resetBtn = document.getElementById('resetParamsBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', resetToDefaults);
        }

        // Help icons
        const helpIcons = document.querySelectorAll('.help-icon');
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
        markExtracted,
        checkParamsChanged,
        applyProfile,
        resetToDefaults,
        defaults,
    };
})();
