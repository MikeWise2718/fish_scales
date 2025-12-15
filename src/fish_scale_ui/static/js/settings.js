/**
 * Fish Scale Measurement UI - Settings Management
 * Handles loading/saving user preferences to localStorage
 */

window.settings = (function() {
    const STORAGE_KEY = 'fishScaleSettings';

    // Default settings
    const defaults = {
        // Navigation
        scrollWheelZoom: true,
        // Overlay display
        showTubercleIds: false,
        idTextSize: 12,
        tubercleColor: '#00ffff',
        connectionColor: '#ffff00', // Yellow for ITC (intertubercular connections)
        connectionEndpoint: 'center', // 'center' or 'edge'
        // Calibration scale display
        showCalibrationScale: false,
        scalePosition: 'bottom-left', // top-left, top-center, top-right, middle-left, middle-right, bottom-left, bottom-center, bottom-right
        // Panel width
        tabsPanelWidth: 400,
    };

    // Current settings
    let current = { ...defaults };

    function init() {
        // Load from localStorage
        load();

        // Bind UI elements
        bindUI();

        // Apply settings to UI
        applyToUI();

        // Init collapsible groups
        initCollapsibleGroups();

        // Init panel resizer
        initPanelResizer();
    }

    function load() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                current = { ...defaults, ...parsed };
            }
        } catch (e) {
            console.warn('Failed to load settings:', e);
            current = { ...defaults };
        }
    }

    function save() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
        } catch (e) {
            console.warn('Failed to save settings:', e);
        }
    }

    function get(key) {
        return current[key];
    }

    function set(key, value) {
        current[key] = value;
        save();

        // Notify listeners
        window.dispatchEvent(new CustomEvent('settingChanged', {
            detail: { key, value }
        }));

        // Re-render overlay if display setting changed
        // Note: showTubercleIds and showCalibrationScale only affect defaults for new images
        // The toggle checkboxes under the image control current visibility
        if (['idTextSize', 'tubercleColor', 'connectionColor', 'connectionEndpoint', 'scalePosition'].includes(key)) {
            if (window.overlay && window.overlay.render) {
                window.overlay.render();
            }
        }
    }

    function reset() {
        current = { ...defaults };
        save();
        applyToUI();

        // Notify about all changes
        Object.keys(defaults).forEach(key => {
            window.dispatchEvent(new CustomEvent('settingChanged', {
                detail: { key, value: defaults[key] }
            }));
        });

        // Re-initialize toggle states and re-render overlay
        if (window.overlay && window.overlay.initToggleStates) {
            window.overlay.initToggleStates();
        }
        if (window.overlay && window.overlay.render) {
            window.overlay.render();
        }

        if (window.app && window.app.showToast) {
            window.app.showToast('Settings reset to defaults', 'success');
        }
    }

    function bindUI() {
        // Scroll wheel zoom checkbox
        const scrollWheelZoomEl = document.getElementById('scrollWheelZoom');
        if (scrollWheelZoomEl) {
            scrollWheelZoomEl.addEventListener('change', function() {
                set('scrollWheelZoom', this.checked);
            });
        }

        // Show tubercle IDs checkbox
        const showTubercleIdsEl = document.getElementById('showTubercleIds');
        if (showTubercleIdsEl) {
            showTubercleIdsEl.addEventListener('change', function() {
                set('showTubercleIds', this.checked);
            });
        }

        // ID text size slider
        const idTextSizeEl = document.getElementById('idTextSize');
        const idTextSizeValueEl = document.getElementById('idTextSizeValue');
        if (idTextSizeEl) {
            idTextSizeEl.addEventListener('input', function() {
                if (idTextSizeValueEl) {
                    idTextSizeValueEl.textContent = this.value + 'px';
                }
            });
            idTextSizeEl.addEventListener('change', function() {
                set('idTextSize', parseInt(this.value));
            });
        }

        // Tubercle color
        const tubercleColorPicker = document.getElementById('tubercleColorPicker');
        const tubercleColorText = document.getElementById('tubercleColorText');
        if (tubercleColorPicker) {
            tubercleColorPicker.addEventListener('input', function() {
                if (tubercleColorText) {
                    tubercleColorText.value = this.value;
                }
                set('tubercleColor', this.value);
            });
        }
        if (tubercleColorText) {
            tubercleColorText.addEventListener('change', function() {
                const color = this.value;
                if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
                    if (tubercleColorPicker) {
                        tubercleColorPicker.value = color;
                    }
                    set('tubercleColor', color);
                }
            });
        }

        // Connection color
        const connectionColorPicker = document.getElementById('connectionColorPicker');
        const connectionColorText = document.getElementById('connectionColorText');
        if (connectionColorPicker) {
            connectionColorPicker.addEventListener('input', function() {
                if (connectionColorText) {
                    connectionColorText.value = this.value;
                }
                set('connectionColor', this.value);
            });
        }
        if (connectionColorText) {
            connectionColorText.addEventListener('change', function() {
                const color = this.value;
                if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
                    if (connectionColorPicker) {
                        connectionColorPicker.value = color;
                    }
                    set('connectionColor', color);
                }
            });
        }

        // Connection endpoint radio buttons
        const connectionToCenterEl = document.getElementById('connectionToCenter');
        const connectionToEdgeEl = document.getElementById('connectionToEdge');
        if (connectionToCenterEl) {
            connectionToCenterEl.addEventListener('change', function() {
                if (this.checked) set('connectionEndpoint', 'center');
            });
        }
        if (connectionToEdgeEl) {
            connectionToEdgeEl.addEventListener('change', function() {
                if (this.checked) set('connectionEndpoint', 'edge');
            });
        }

        // Show calibration scale checkbox
        const showCalibrationScaleEl = document.getElementById('showCalibrationScale');
        if (showCalibrationScaleEl) {
            showCalibrationScaleEl.addEventListener('change', function() {
                set('showCalibrationScale', this.checked);
                // Show/hide scale position setting based on checkbox
                const scalePositionSetting = document.getElementById('scalePositionSetting');
                if (scalePositionSetting) {
                    scalePositionSetting.style.display = this.checked ? 'block' : 'none';
                }
            });
        }

        // Scale position dropdown
        const scalePositionEl = document.getElementById('scalePosition');
        if (scalePositionEl) {
            scalePositionEl.addEventListener('change', function() {
                set('scalePosition', this.value);
            });
        }

        // Reset button
        const resetBtn = document.getElementById('resetSettingsBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', reset);
        }
    }

    function applyToUI() {
        // Scroll wheel zoom
        const scrollWheelZoomEl = document.getElementById('scrollWheelZoom');
        if (scrollWheelZoomEl) {
            scrollWheelZoomEl.checked = current.scrollWheelZoom;
        }

        // Show tubercle IDs
        const showTubercleIdsEl = document.getElementById('showTubercleIds');
        if (showTubercleIdsEl) {
            showTubercleIdsEl.checked = current.showTubercleIds;
        }

        // ID text size
        const idTextSizeEl = document.getElementById('idTextSize');
        const idTextSizeValueEl = document.getElementById('idTextSizeValue');
        if (idTextSizeEl) {
            idTextSizeEl.value = current.idTextSize;
            if (idTextSizeValueEl) {
                idTextSizeValueEl.textContent = current.idTextSize + 'px';
            }
        }

        // Tubercle color
        const tubercleColorPicker = document.getElementById('tubercleColorPicker');
        const tubercleColorText = document.getElementById('tubercleColorText');
        if (tubercleColorPicker) {
            tubercleColorPicker.value = current.tubercleColor;
        }
        if (tubercleColorText) {
            tubercleColorText.value = current.tubercleColor;
        }

        // Connection color
        const connectionColorPicker = document.getElementById('connectionColorPicker');
        const connectionColorText = document.getElementById('connectionColorText');
        if (connectionColorPicker) {
            connectionColorPicker.value = current.connectionColor;
        }
        if (connectionColorText) {
            connectionColorText.value = current.connectionColor;
        }

        // Connection endpoint
        const connectionToCenterEl = document.getElementById('connectionToCenter');
        const connectionToEdgeEl = document.getElementById('connectionToEdge');
        if (current.connectionEndpoint === 'center') {
            if (connectionToCenterEl) connectionToCenterEl.checked = true;
        } else {
            if (connectionToEdgeEl) connectionToEdgeEl.checked = true;
        }

        // Show calibration scale
        const showCalibrationScaleEl = document.getElementById('showCalibrationScale');
        if (showCalibrationScaleEl) {
            showCalibrationScaleEl.checked = current.showCalibrationScale;
        }

        // Scale position
        const scalePositionEl = document.getElementById('scalePosition');
        if (scalePositionEl) {
            scalePositionEl.value = current.scalePosition;
        }

        // Show/hide scale position setting based on checkbox
        const scalePositionSetting = document.getElementById('scalePositionSetting');
        if (scalePositionSetting) {
            scalePositionSetting.style.display = current.showCalibrationScale ? 'block' : 'none';
        }

        // Panel width
        const tabsPanel = document.getElementById('tabsPanel');
        if (tabsPanel && current.tabsPanelWidth) {
            tabsPanel.style.width = current.tabsPanelWidth + 'px';
        }
    }

    function initCollapsibleGroups() {
        const groups = document.querySelectorAll('.settings-group');
        groups.forEach(group => {
            const header = group.querySelector('.settings-group-header');
            if (header) {
                header.addEventListener('click', () => {
                    group.classList.toggle('collapsed');
                });
            }
        });
    }

    function initPanelResizer() {
        const resizer = document.getElementById('panelResizer');
        const tabsPanel = document.getElementById('tabsPanel');
        if (!resizer || !tabsPanel) return;

        let isResizing = false;
        let startX, startWidth;

        resizer.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startWidth = tabsPanel.offsetWidth;
            resizer.classList.add('resizing');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;

            // Calculate new width (resizer is on left of tabs panel)
            const dx = startX - e.clientX;
            const maxWidth = window.innerWidth * 0.8; // Allow up to 80% of viewport
            const newWidth = Math.max(300, Math.min(maxWidth, startWidth + dx));
            tabsPanel.style.width = newWidth + 'px';
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                resizer.classList.remove('resizing');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';

                // Save the new width
                set('tabsPanelWidth', tabsPanel.offsetWidth);
            }
        });
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        get,
        set,
        reset,
        load,
        save
    };
})();
