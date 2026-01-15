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
        boundaryTubercleColor: '#ff8800', // Orange for boundary nodes
        connectionColor: '#ffff00', // Yellow for ITC (intertubercular connections)
        gridColor: '#ff88ff', // Light magenta for coordinate grid
        gridOpacity: 0.35, // Grid line opacity (0.0 - 1.0)
        connectionEndpoint: 'center', // 'center' or 'edge'
        tubercleColorMode: 'source', // 'uniform', 'source', 'boundary'
        // Calibration scale display
        showCalibrationScale: false,
        scalePosition: 'bottom-left', // top-left, top-center, top-right, middle-left, middle-right, bottom-left, bottom-center, bottom-right
        // Hexagonalness coefficients (must sum to 1.0)
        hexSpacingWeight: 0.40,
        hexDegreeWeight: 0.45,
        hexEdgeRatioWeight: 0.15,
        // Panel width
        tabsPanelWidth: 400,
        // Theme settings
        panelTheme: 'dark', // 'dark', 'light', or 'custom'
        // Custom theme colors (used when panelTheme === 'custom')
        customPanelBg: '#1e293b',
        customPanelBgAlt: '#1a1a2e',
        customPanelText: '#e2e8f0',
        customPanelTextMuted: '#94a3b8',
        customPanelTextDim: '#64748b',
        customPanelBorder: '#334155',
        customPanelGrid: '#333344',
        // Editor settings
        'editor.autoSizeEnabled': false, // Auto-size tubercles from image analysis
        'editor.autoSizeRegionFactor': 6, // Region size multiplier for auto-size detection
        'editor.autoSizeShowRegion': false, // Show analyzed region as visual feedback
    };

    // Predefined theme color palettes
    const THEMES = {
        dark: {
            panelBg: '#1e293b',
            panelBgAlt: '#1a1a2e',
            panelText: '#e2e8f0',
            panelTextMuted: '#94a3b8',
            panelTextDim: '#64748b',
            panelBorder: '#334155',
            panelGrid: '#333344',
            setNameColor: '#93c5fd',      // Light blue - good contrast on dark
            hexValueColor: '#fbbf24',     // Amber - good contrast on dark
        },
        light: {
            panelBg: '#f1f5f9',
            panelBgAlt: '#e2e8f0',
            panelText: '#1e293b',
            panelTextMuted: '#475569',
            panelTextDim: '#64748b',
            panelBorder: '#cbd5e1',
            panelGrid: '#94a3b8',
            setNameColor: '#1d4ed8',      // Darker blue - good contrast on light
            hexValueColor: '#b45309',     // Darker amber - good contrast on light
        },
    };

    // Current settings
    let current = { ...defaults };

    function init() {
        // Load from localStorage
        load();

        // Bind UI elements
        bindUI();

        // Bind theme color UI
        bindThemeColorUI();

        // Apply settings to UI
        applyToUI();

        // Apply theme colors to CSS variables
        applyThemeColors();

        // Init collapsible groups
        initCollapsibleGroups();

        // Init panel resizer
        initPanelResizer();

        // Init hexagonalness calculation display listener
        initHexCalcListener();
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
        if (['idTextSize', 'tubercleColor', 'connectionColor', 'gridColor', 'gridOpacity', 'connectionEndpoint', 'scalePosition'].includes(key)) {
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

        // Also reset and apply theme colors
        applyThemeColorsToUI();
        applyThemeColors();
    }

    // ============================================
    // Theme Color Functions
    // ============================================

    /**
     * Apply theme colors to CSS custom properties.
     * This updates the CSS variables that control the dark panel appearance.
     */
    function applyThemeColors() {
        const root = document.documentElement;
        let colors;

        if (current.panelTheme === 'custom') {
            colors = {
                panelBg: current.customPanelBg,
                panelBgAlt: current.customPanelBgAlt,
                panelText: current.customPanelText,
                panelTextMuted: current.customPanelTextMuted,
                panelTextDim: current.customPanelTextDim,
                panelBorder: current.customPanelBorder,
                panelGrid: current.customPanelGrid,
            };
        } else {
            colors = THEMES[current.panelTheme] || THEMES.dark;
        }

        root.style.setProperty('--panel-dark-bg', colors.panelBg);
        root.style.setProperty('--panel-dark-bg-alt', colors.panelBgAlt);
        root.style.setProperty('--panel-dark-text', colors.panelText);
        root.style.setProperty('--panel-dark-text-muted', colors.panelTextMuted);
        root.style.setProperty('--panel-dark-text-dim', colors.panelTextDim);
        root.style.setProperty('--panel-dark-border', colors.panelBorder);
        root.style.setProperty('--panel-dark-grid', colors.panelGrid);
        root.style.setProperty('--stats-bar-set-color', colors.setNameColor || '#93c5fd');
        root.style.setProperty('--stats-bar-hex-color', colors.hexValueColor || '#fbbf24');

        // Dispatch event so canvas-based components can redraw
        window.dispatchEvent(new CustomEvent('themeColorsChanged'));
    }

    /**
     * Bind theme color UI elements (radio buttons and color pickers).
     */
    function bindThemeColorUI() {
        // Theme mode radio buttons
        const themeRadios = document.querySelectorAll('input[name="panelTheme"]');
        themeRadios.forEach(radio => {
            radio.addEventListener('change', function() {
                set('panelTheme', this.value);
                toggleCustomColorsVisibility(this.value === 'custom');
                applyThemeColors();
            });
        });

        // Custom color pickers
        const colorSettings = [
            { picker: 'panelBgColorPicker', text: 'panelBgColorText', key: 'customPanelBg' },
            { picker: 'panelBgAltColorPicker', text: 'panelBgAltColorText', key: 'customPanelBgAlt' },
            { picker: 'panelTextColorPicker', text: 'panelTextColorText', key: 'customPanelText' },
            { picker: 'panelTextMutedColorPicker', text: 'panelTextMutedColorText', key: 'customPanelTextMuted' },
            { picker: 'panelTextDimColorPicker', text: 'panelTextDimColorText', key: 'customPanelTextDim' },
            { picker: 'panelBorderColorPicker', text: 'panelBorderColorText', key: 'customPanelBorder' },
            { picker: 'panelGridColorPicker', text: 'panelGridColorText', key: 'customPanelGrid' },
        ];

        colorSettings.forEach(({ picker, text, key }) => {
            bindThemeColorPicker(picker, text, key);
        });

        // Reset theme colors button
        const resetBtn = document.getElementById('resetThemeColorsBtn');
        if (resetBtn) {
            resetBtn.addEventListener('click', resetThemeColors);
        }
    }

    /**
     * Bind a color picker and text input pair for theme colors.
     */
    function bindThemeColorPicker(pickerId, textId, settingKey) {
        const picker = document.getElementById(pickerId);
        const textInput = document.getElementById(textId);

        if (picker) {
            picker.addEventListener('input', function() {
                if (textInput) {
                    textInput.value = this.value;
                }
                set(settingKey, this.value);
                applyThemeColors();
            });
        }

        if (textInput) {
            textInput.addEventListener('change', function() {
                const color = this.value;
                if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
                    if (picker) {
                        picker.value = color;
                    }
                    set(settingKey, color);
                    applyThemeColors();
                }
            });
        }
    }

    /**
     * Toggle visibility of custom color options.
     */
    function toggleCustomColorsVisibility(show) {
        const customSection = document.getElementById('customThemeColors');
        if (customSection) {
            customSection.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * Reset theme colors to defaults.
     */
    function resetThemeColors() {
        set('panelTheme', defaults.panelTheme);
        set('customPanelBg', defaults.customPanelBg);
        set('customPanelBgAlt', defaults.customPanelBgAlt);
        set('customPanelText', defaults.customPanelText);
        set('customPanelTextMuted', defaults.customPanelTextMuted);
        set('customPanelTextDim', defaults.customPanelTextDim);
        set('customPanelBorder', defaults.customPanelBorder);
        set('customPanelGrid', defaults.customPanelGrid);

        applyThemeColorsToUI();
        applyThemeColors();

        if (window.app && window.app.showToast) {
            window.app.showToast('Theme colors reset to defaults', 'success');
        }
    }

    /**
     * Apply theme color settings to UI elements.
     */
    function applyThemeColorsToUI() {
        // Set radio button based on current theme
        const themeValue = current.panelTheme || 'dark';
        const themeRadio = document.getElementById('panelTheme' + capitalize(themeValue));
        if (themeRadio) {
            themeRadio.checked = true;
        }

        // Toggle custom colors visibility
        toggleCustomColorsVisibility(themeValue === 'custom');

        // Set custom color pickers
        setColorPickerValue('panelBgColorPicker', 'panelBgColorText', current.customPanelBg);
        setColorPickerValue('panelBgAltColorPicker', 'panelBgAltColorText', current.customPanelBgAlt);
        setColorPickerValue('panelTextColorPicker', 'panelTextColorText', current.customPanelText);
        setColorPickerValue('panelTextMutedColorPicker', 'panelTextMutedColorText', current.customPanelTextMuted);
        setColorPickerValue('panelTextDimColorPicker', 'panelTextDimColorText', current.customPanelTextDim);
        setColorPickerValue('panelBorderColorPicker', 'panelBorderColorText', current.customPanelBorder);
        setColorPickerValue('panelGridColorPicker', 'panelGridColorText', current.customPanelGrid);
    }

    /**
     * Set color picker and text input values.
     */
    function setColorPickerValue(pickerId, textId, value) {
        const picker = document.getElementById(pickerId);
        const text = document.getElementById(textId);
        if (picker) picker.value = value;
        if (text) text.value = value;
    }

    /**
     * Capitalize first letter of a string.
     */
    function capitalize(str) {
        return str.charAt(0).toUpperCase() + str.slice(1);
    }

    // ============================================
    // End Theme Color Functions
    // ============================================

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

        // Grid color
        const gridColorPicker = document.getElementById('gridColorPicker');
        const gridColorText = document.getElementById('gridColorText');
        if (gridColorPicker) {
            gridColorPicker.addEventListener('input', function() {
                if (gridColorText) {
                    gridColorText.value = this.value;
                }
                set('gridColor', this.value);
            });
        }
        if (gridColorText) {
            gridColorText.addEventListener('change', function() {
                const color = this.value;
                if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
                    if (gridColorPicker) {
                        gridColorPicker.value = color;
                    }
                    set('gridColor', color);
                }
            });
        }

        // Grid opacity slider
        const gridOpacitySlider = document.getElementById('gridOpacitySlider');
        const gridOpacityValue = document.getElementById('gridOpacityValue');
        if (gridOpacitySlider) {
            gridOpacitySlider.addEventListener('input', function() {
                const opacity = parseFloat(this.value);
                if (gridOpacityValue) {
                    gridOpacityValue.textContent = Math.round(opacity * 100) + '%';
                }
                set('gridOpacity', opacity);
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

        // Tubercle color mode radio buttons
        const colorModes = ['colorModeUniform', 'colorModeSource', 'colorModeBoundary'];
        colorModes.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', function() {
                    if (this.checked) {
                        set('tubercleColorMode', this.value);
                        // Update overlay color mode
                        if (window.overlay && window.overlay.setColorMode) {
                            window.overlay.setColorMode(this.value);
                        }
                    }
                });
            }
        });

        // Boundary tubercle color picker
        const boundaryColorPicker = document.getElementById('boundaryTubercleColorPicker');
        const boundaryColorText = document.getElementById('boundaryTubercleColorText');
        if (boundaryColorPicker) {
            boundaryColorPicker.addEventListener('input', function() {
                if (boundaryColorText) {
                    boundaryColorText.value = this.value;
                }
                set('boundaryTubercleColor', this.value);
            });
        }
        if (boundaryColorText) {
            boundaryColorText.addEventListener('change', function() {
                const color = this.value;
                if (/^#[0-9A-Fa-f]{6}$/.test(color)) {
                    if (boundaryColorPicker) {
                        boundaryColorPicker.value = color;
                    }
                    set('boundaryTubercleColor', color);
                }
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

        // Hexagonalness coefficient sliders
        bindHexSlider('hexSpacingWeight', 'hexSpacingWeightValue');
        bindHexSlider('hexDegreeWeight', 'hexDegreeWeightValue');
        bindHexSlider('hexEdgeRatioWeight', 'hexEdgeRatioWeightValue');

        // Reset hexagonalness to defaults button
        const resetHexBtn = document.getElementById('resetHexWeightsBtn');
        if (resetHexBtn) {
            resetHexBtn.addEventListener('click', resetHexWeights);
        }

        // Normalize hexagonalness weights button
        const normalizeHexBtn = document.getElementById('normalizeHexWeightsBtn');
        if (normalizeHexBtn) {
            normalizeHexBtn.addEventListener('click', normalizeHexWeights);
        }
    }

    function bindHexSlider(sliderId, valueId) {
        const slider = document.getElementById(sliderId);
        const valueEl = document.getElementById(valueId);
        if (slider) {
            slider.addEventListener('input', function() {
                if (valueEl) {
                    valueEl.textContent = parseFloat(this.value).toFixed(2);
                }
                updateHexWeightsSum();
            });
            slider.addEventListener('change', function() {
                set(sliderId, parseFloat(this.value));
                recalculateHexagonalness();
            });
        }
    }

    function updateHexWeightsSum() {
        const spacing = parseFloat(document.getElementById('hexSpacingWeight')?.value || 0);
        const degree = parseFloat(document.getElementById('hexDegreeWeight')?.value || 0);
        const edgeRatio = parseFloat(document.getElementById('hexEdgeRatioWeight')?.value || 0);
        const sum = spacing + degree + edgeRatio;
        const sumEl = document.getElementById('hexWeightsSum');
        if (sumEl) {
            sumEl.textContent = sum.toFixed(2);
            sumEl.classList.toggle('sum-warning', Math.abs(sum - 1.0) > 0.01);
        }
    }

    function resetHexWeights() {
        set('hexSpacingWeight', defaults.hexSpacingWeight);
        set('hexDegreeWeight', defaults.hexDegreeWeight);
        set('hexEdgeRatioWeight', defaults.hexEdgeRatioWeight);
        applyHexWeightsToUI();
        recalculateHexagonalness();
        if (window.app && window.app.showToast) {
            window.app.showToast('Hexagonalness weights reset to defaults', 'success');
        }
    }

    function normalizeHexWeights() {
        const spacing = current.hexSpacingWeight;
        const degree = current.hexDegreeWeight;
        const edgeRatio = current.hexEdgeRatioWeight;
        const sum = spacing + degree + edgeRatio;

        if (sum === 0) {
            if (window.app && window.app.showToast) {
                window.app.showToast('Cannot normalize: sum is zero', 'error');
            }
            return;
        }

        set('hexSpacingWeight', spacing / sum);
        set('hexDegreeWeight', degree / sum);
        set('hexEdgeRatioWeight', edgeRatio / sum);
        applyHexWeightsToUI();
        recalculateHexagonalness();
        if (window.app && window.app.showToast) {
            window.app.showToast('Hexagonalness weights normalized', 'success');
        }
    }

    function applyHexWeightsToUI() {
        const spacingSlider = document.getElementById('hexSpacingWeight');
        const spacingValue = document.getElementById('hexSpacingWeightValue');
        if (spacingSlider) {
            spacingSlider.value = current.hexSpacingWeight;
            if (spacingValue) spacingValue.textContent = current.hexSpacingWeight.toFixed(2);
        }

        const degreeSlider = document.getElementById('hexDegreeWeight');
        const degreeValue = document.getElementById('hexDegreeWeightValue');
        if (degreeSlider) {
            degreeSlider.value = current.hexDegreeWeight;
            if (degreeValue) degreeValue.textContent = current.hexDegreeWeight.toFixed(2);
        }

        const edgeRatioSlider = document.getElementById('hexEdgeRatioWeight');
        const edgeRatioValue = document.getElementById('hexEdgeRatioWeightValue');
        if (edgeRatioSlider) {
            edgeRatioSlider.value = current.hexEdgeRatioWeight;
            if (edgeRatioValue) edgeRatioValue.textContent = current.hexEdgeRatioWeight.toFixed(2);
        }

        updateHexWeightsSum();
    }

    function recalculateHexagonalness() {
        // Trigger recalculation in any module that computes hexagonalness
        window.dispatchEvent(new CustomEvent('hexWeightsChanged'));
        // Update the calculation display
        updateHexCalcDisplay();
    }

    async function updateHexCalcDisplay() {
        const hexEl = document.getElementById('hexCalcValue');

        // Get current weights
        const spacingWeight = current.hexSpacingWeight;
        const degreeWeight = current.hexDegreeWeight;
        const edgeRatioWeight = current.hexEdgeRatioWeight;

        // Fetch hexagonalness from server (single source of truth)
        try {
            const params = new URLSearchParams({
                spacing_weight: spacingWeight,
                degree_weight: degreeWeight,
                edge_ratio_weight: edgeRatioWeight,
            });
            const response = await fetch(`/api/hexagonalness?${params}`);
            const result = await response.json();
            if (hexEl) {
                if (result.hexagonalness_score !== undefined && result.reliability !== 'none') {
                    hexEl.textContent = result.hexagonalness_score.toFixed(6);
                } else {
                    hexEl.textContent = '-';
                }
            }
        } catch (e) {
            if (hexEl) hexEl.textContent = 'error';
        }
    }

    // Listen for data changes to update the calculation display
    function initHexCalcListener() {
        // Update display when hex weights change (already handled in recalculateHexagonalness)
        // Also update when data changes
        document.addEventListener('setChanged', () => {
            setTimeout(updateHexCalcDisplay, 100);
        });
        document.addEventListener('setsLoaded', () => {
            setTimeout(updateHexCalcDisplay, 100);
        });
        document.addEventListener('extractionComplete', () => {
            setTimeout(updateHexCalcDisplay, 100);
        });
        document.addEventListener('dataModified', () => {
            setTimeout(updateHexCalcDisplay, 100);
        });
        document.addEventListener('connectionsRegenerated', () => {
            setTimeout(updateHexCalcDisplay, 100);
        });
        // Initial update
        setTimeout(updateHexCalcDisplay, 500);
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

        // Grid color
        const gridColorPicker = document.getElementById('gridColorPicker');
        const gridColorText = document.getElementById('gridColorText');
        if (gridColorPicker) {
            gridColorPicker.value = current.gridColor;
        }
        if (gridColorText) {
            gridColorText.value = current.gridColor;
        }

        // Grid opacity
        const gridOpacitySlider = document.getElementById('gridOpacitySlider');
        const gridOpacityValue = document.getElementById('gridOpacityValue');
        if (gridOpacitySlider) {
            gridOpacitySlider.value = current.gridOpacity;
        }
        if (gridOpacityValue) {
            gridOpacityValue.textContent = Math.round(current.gridOpacity * 100) + '%';
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

        // Tubercle color mode
        const colorModeRadios = {
            'uniform': document.getElementById('colorModeUniform'),
            'source': document.getElementById('colorModeSource'),
            'boundary': document.getElementById('colorModeBoundary'),
        };
        const selectedColorMode = current.tubercleColorMode || 'source';
        if (colorModeRadios[selectedColorMode]) {
            colorModeRadios[selectedColorMode].checked = true;
        }
        // Apply color mode to overlay
        if (window.overlay && window.overlay.setColorMode) {
            window.overlay.setColorMode(selectedColorMode);
        }

        // Boundary tubercle color
        const boundaryColorPicker = document.getElementById('boundaryTubercleColorPicker');
        const boundaryColorText = document.getElementById('boundaryTubercleColorText');
        if (boundaryColorPicker) {
            boundaryColorPicker.value = current.boundaryTubercleColor;
        }
        if (boundaryColorText) {
            boundaryColorText.value = current.boundaryTubercleColor;
        }

        // Panel width
        const tabsPanel = document.getElementById('tabsPanel');
        if (tabsPanel && current.tabsPanelWidth) {
            tabsPanel.style.width = current.tabsPanelWidth + 'px';
        }

        // Hexagonalness weights
        applyHexWeightsToUI();

        // Theme colors
        applyThemeColorsToUI();
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
