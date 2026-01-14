/**
 * Fish Scale Measurement UI - Editor Module
 * Phase 3: Manual Editing Support
 */

window.editor = (function() {
    // Edit modes
    const EditMode = {
        NONE: 'none',
        ADD_TUB: 'add_tub',
        ADD_ITC: 'add_itc',
        ADD_CHAIN: 'add_chain',  // Add tubercles with auto-connections
        MOVE: 'move',
        DELETE_MULTI_TUB: 'delete_multi_tub',
        DELETE_MULTI_ITC: 'delete_multi_itc',
        AREA_SELECT: 'area_select',  // Area selection mode for multi-select
    };

    // Mode banner configuration
    const ModeBannerConfig = {
        [EditMode.ADD_TUB]: {
            icon: '\u2295',  // ⊕
            title: 'Add Tubercle',
            desc: 'Click on the image to place a new tubercle',
            colorClass: 'mode-add',
        },
        [EditMode.ADD_ITC]: {
            icon: '\u27F7',  // ⟷
            title: 'Add Connection',
            desc: 'Click first tubercle, then click second to connect',
            colorClass: 'mode-add',
        },
        [EditMode.ADD_CHAIN]: {
            icon: '\u26D3',  // ⛓
            title: 'Chain Mode',
            desc: 'Click to add connected tubercles. Arrow keys to navigate.',
            colorClass: 'mode-add',
        },
        [EditMode.MOVE]: {
            icon: '\u2725',  // ✥
            title: 'Move Tubercle',
            desc: 'Click on image to move the selected tubercle',
            colorClass: 'mode-move',
        },
        [EditMode.DELETE_MULTI_TUB]: {
            icon: '\u2296',  // ⊖
            title: 'Delete Tubercles',
            desc: 'Click on tubercles to delete them',
            colorClass: 'mode-delete',
        },
        [EditMode.DELETE_MULTI_ITC]: {
            icon: '\u2702',  // ✂
            title: 'Delete Connections',
            desc: 'Click on connections to delete them',
            colorClass: 'mode-delete',
        },
        [EditMode.AREA_SELECT]: {
            icon: '\u25A2',  // ▢
            title: 'Area Select',
            desc: 'Click and drag to select multiple items',
            colorClass: 'mode-select',
        },
    };

    // Current state
    let currentMode = EditMode.NONE;
    let pendingFirstTub = null; // For ITC creation - first selected tubercle
    let chainParents = {}; // For chain mode - maps tubercle ID to its parent ID
    let chainCurrentId = null; // Currently selected tubercle in chain mode
    let chainNeighbors = []; // Neighbor tubercle IDs for navigation
    let chainNeighborIndex = -1; // Currently highlighted neighbor (-1 = none)
    let allowDeleteWithoutConfirm = false;
    let defaultRadius = null; // Will be set from mean diameter
    let userDefaultDiameterUm = null; // User-specified default diameter in µm (from input field)
    let autoSizeEnabled = false; // Whether to auto-size tubercles from image analysis
    let autoSizeRegionFactor = 6; // Region size multiplier for auto-size detection
    let autoSizeShowRegion = false; // Whether to show the analyzed region as visual feedback

    // Data references (synced with overlay and data modules)
    let tubercles = [];
    let edges = [];
    let nextTubId = 1;

    // Get current calibration for conversions
    function getCalibration() {
        return window.calibration?.getCurrentCalibration();
    }

    /**
     * Get the effective default radius for new tubercles.
     * Uses user-specified diameter if set, otherwise falls back to calculated mean.
     * @returns {number} Radius in pixels
     */
    function getEffectiveDefaultRadius() {
        // If user has specified a diameter in µm, convert to radius in pixels
        if (userDefaultDiameterUm !== null && userDefaultDiameterUm > 0) {
            const calibration = getCalibration();
            const umPerPx = calibration?.um_per_px;
            if (umPerPx && umPerPx > 0) {
                return (userDefaultDiameterUm / 2) / umPerPx; // diameter -> radius, µm -> px
            }
        }
        // Fall back to calculated default
        return defaultRadius || 10;
    }

    /**
     * Set the user-specified default diameter (in µm)
     * @param {number|null} diameterUm - Diameter in micrometers, or null to use auto
     */
    function setDefaultDiameterUm(diameterUm) {
        userDefaultDiameterUm = diameterUm;
        updateDefaultDiameterHint();
    }

    /**
     * Get the user-specified default diameter (in µm)
     * @returns {number|null}
     */
    function getDefaultDiameterUm() {
        return userDefaultDiameterUm;
    }

    /**
     * Update the hint text for the default diameter input
     */
    function updateDefaultDiameterHint() {
        const hint = document.getElementById('defaultDiameterHint');
        const input = document.getElementById('defaultTubercleDiameter');
        if (!hint) return;

        const calibration = getCalibration();
        const umPerPx = calibration?.um_per_px;

        if (!umPerPx || umPerPx <= 0) {
            hint.textContent = 'Requires calibration';
            hint.style.color = 'var(--panel-dark-text-dim)';
            if (input) input.disabled = true;
            return;
        }

        if (input) input.disabled = false;

        // Show current auto value if field is empty
        if (!userDefaultDiameterUm && tubercles.length > 0) {
            const meanDiamUm = tubercles.reduce((sum, t) => sum + (t.radius_px * 2 * umPerPx), 0) / tubercles.length;
            hint.textContent = `Auto: ${meanDiamUm.toFixed(3)} µm`;
            hint.style.color = 'var(--panel-dark-text-muted)';
        } else if (!userDefaultDiameterUm) {
            const defaultDiamUm = (defaultRadius || 10) * 2 * umPerPx;
            hint.textContent = `Default: ${defaultDiamUm.toFixed(3)} µm`;
            hint.style.color = 'var(--panel-dark-text-muted)';
        } else {
            hint.textContent = '';
        }
    }

    /**
     * Update the hint and enabled state for auto-size checkbox
     */
    function updateAutoSizeHint() {
        const hint = document.getElementById('autoSizeHint');
        const checkbox = document.getElementById('autoSizeEnabled');
        if (!hint || !checkbox) return;

        const calibration = getCalibration();
        const umPerPx = calibration?.um_per_px;

        if (!umPerPx || umPerPx <= 0) {
            hint.textContent = 'Requires calibration';
            hint.style.color = 'var(--panel-dark-text-dim)';
            checkbox.disabled = true;
            return;
        }

        checkbox.disabled = false;
        hint.textContent = 'Uses current detection parameters';
        hint.style.color = 'var(--panel-dark-text-muted)';
    }

    /**
     * Set auto-size enabled state
     * @param {boolean} enabled
     */
    function setAutoSizeEnabled(enabled) {
        autoSizeEnabled = enabled;
        // Persist to settings
        window.settings?.set('editor.autoSizeEnabled', enabled);
    }

    /**
     * Get auto-size enabled state
     * @returns {boolean}
     */
    function isAutoSizeEnabled() {
        return autoSizeEnabled;
    }

    /**
     * Analyze a point to get auto-sized diameter
     * @param {number} x - X coordinate in pixels
     * @param {number} y - Y coordinate in pixels
     * @returns {Promise<{diameter_px: number, diameter_um: number, radius_px: number, center_x: number, center_y: number} | null>}
     */
    async function analyzePointForSize(x, y) {
        const params = window.configure?.getParams() || {};

        try {
            const response = await fetch('/api/analyze-point', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    x,
                    y,
                    parameters: params,
                    region_factor: autoSizeRegionFactor
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Auto-size API error:', response.status, errorText);
                window.app?.showToast(`Auto-size failed: ${response.status}`, 'warning');
                return null;
            }

            const result = await response.json();

            // Show region echo if enabled
            if (autoSizeShowRegion && result.region) {
                const selectedBlob = result.detected ? {
                    center_x: result.center_x,
                    center_y: result.center_y,
                    radius_px: result.radius_px,
                } : null;
                showRegionEcho(result.region, result.all_blobs || [], selectedBlob);
            }

            if (result.success && result.detected) {
                const analysis = {
                    diameter_px: result.diameter_px,
                    diameter_um: result.diameter_um,
                    radius_px: result.radius_px,
                    center_x: result.center_x,
                    center_y: result.center_y,
                    circularity: result.circularity,
                };
                // Include ellipse parameters if available
                if (result.major_axis_px !== undefined) {
                    analysis.major_axis_px = result.major_axis_px;
                    analysis.minor_axis_px = result.minor_axis_px;
                    analysis.major_axis_um = result.major_axis_um;
                    analysis.minor_axis_um = result.minor_axis_um;
                    analysis.orientation = result.orientation;
                    analysis.eccentricity = result.eccentricity;
                }
                return analysis;
            }
            // No blob detected - this is fine, will fall back to default
            if (result.reason) {
                console.log('Auto-size: no blob detected -', result.reason);
            }
            return null;
        } catch (error) {
            console.error('Auto-size analysis failed:', error);
            window.app?.showToast(`Auto-size error: ${error.message}`, 'warning');
            return null;
        }
    }

    /**
     * Show a temporary rectangle indicating the analyzed region with detected blobs
     * @param {Object} region - Region bounds {x_min, y_min, x_max, y_max}
     * @param {Array} allBlobs - All detected blobs [{center_x, center_y, radius_px}, ...]
     * @param {Object|null} selectedBlob - The blob that was selected (closest to click), or null
     */
    function showRegionEcho(region, allBlobs, selectedBlob) {
        // Use overlay module to draw the region and blobs
        window.overlay?.showTemporaryRegion(
            region.x_min,
            region.y_min,
            region.x_max - region.x_min,
            region.y_max - region.y_min,
            3000, // Duration in ms
            allBlobs,
            selectedBlob
        );
    }

    /**
     * Initialize editor with current data
     */
    function setData(newTubercles, newEdges) {
        tubercles = newTubercles || [];
        edges = newEdges || [];

        // Calculate next ID
        if (tubercles.length > 0) {
            nextTubId = Math.max(...tubercles.map(t => t.id)) + 1;
        } else {
            nextTubId = 1;
        }

        // Calculate default radius from mean diameter
        if (tubercles.length > 0) {
            const meanDiamPx = tubercles.reduce((sum, t) => sum + t.radius_px * 2, 0) / tubercles.length;
            defaultRadius = meanDiamPx / 2;
        } else {
            // Default to 10 pixels if no data
            defaultRadius = 10;
        }

        // Reset mode
        setMode(EditMode.NONE);

        // Update regenerate button state
        updateRegenerateButtonState();

        // Update default diameter hint (shows auto value based on current data)
        updateDefaultDiameterHint();
    }

    /**
     * Update regenerate connections button enabled state
     */
    function updateRegenerateButtonState() {
        const btn = document.getElementById('regenerateConnectionsBtn');
        if (btn) {
            // Enable if we have at least 2 tubercles
            btn.disabled = tubercles.length < 2;
        }
    }

    /**
     * Get current data
     */
    function getData() {
        return { tubercles, edges };
    }

    /**
     * Set the current edit mode
     */
    function setMode(mode) {
        const previousMode = currentMode;
        currentMode = mode;
        pendingFirstTub = null;

        // Reset chain when entering chain mode, or when leaving it
        if (mode === EditMode.ADD_CHAIN) {
            chainParents = {};
            chainCurrentId = null;
            chainNeighbors = [];
            chainNeighborIndex = -1;
            window.overlay?.setHighlightedEdge(null);
        } else if (previousMode === EditMode.ADD_CHAIN) {
            chainParents = {};
            chainCurrentId = null;
            chainNeighbors = [];
            chainNeighborIndex = -1;
            window.overlay?.setHighlightedEdge(null);
        }

        // Update UI
        updateModeUI();

        // Auto-enable toggles if needed
        if (mode === EditMode.ADD_TUB || mode === EditMode.MOVE || mode === EditMode.DELETE_MULTI_TUB) {
            ensureTubesVisible();
        } else if (mode === EditMode.ADD_ITC || mode === EditMode.DELETE_MULTI_ITC) {
            ensureLinksVisible();
            if (mode === EditMode.ADD_ITC) {
                ensureTubesVisible(); // Need to see tubes to click them
            }
        } else if (mode === EditMode.ADD_CHAIN) {
            ensureTubesVisible();
            ensureLinksVisible();
        } else if (mode === EditMode.AREA_SELECT) {
            // Area select should show both tubes and links
            ensureTubesVisible();
            ensureLinksVisible();
        }

        // Update cursor
        updateCursor();

        // Dispatch event
        document.dispatchEvent(new CustomEvent('editModeChanged', {
            detail: { mode, previousMode }
        }));
    }

    /**
     * Get the current edit mode
     */
    function getMode() {
        return currentMode;
    }

    /**
     * Cancel the current mode
     */
    function cancelMode() {
        setMode(EditMode.NONE);
        window.overlay?.deselect();
    }

    /**
     * Ensure tubes toggle is on
     */
    function ensureTubesVisible() {
        const toggle = document.getElementById('toggleTubes');
        if (toggle && !toggle.checked) {
            toggle.checked = true;
            toggle.dispatchEvent(new Event('change'));
            window.app?.showToast('Tubes enabled for editing', 'info');
        }
    }

    /**
     * Ensure links toggle is on
     */
    function ensureLinksVisible() {
        const toggle = document.getElementById('toggleLinks');
        if (toggle && !toggle.checked) {
            toggle.checked = true;
            toggle.dispatchEvent(new Event('change'));
            window.app?.showToast('Links enabled for editing', 'info');
        }
    }

    /**
     * Check if tubes are visible
     */
    function areTubesVisible() {
        const toggle = document.getElementById('toggleTubes');
        return toggle ? toggle.checked : true;
    }

    /**
     * Check if links are visible
     */
    function areLinksVisible() {
        const toggle = document.getElementById('toggleLinks');
        return toggle ? toggle.checked : true;
    }

    /**
     * Update the mode banner above the image
     */
    function updateModeBanner() {
        const banner = document.getElementById('editModeBanner');
        const iconEl = document.getElementById('editModeBannerIcon');
        const titleEl = document.getElementById('editModeBannerTitle');
        const descEl = document.getElementById('editModeBannerDesc');
        const container = document.getElementById('imageContainer');

        if (!banner) return;

        // Remove all mode classes from banner and container
        banner.classList.remove('mode-add', 'mode-delete', 'mode-move', 'mode-select');
        if (container) {
            container.classList.remove('edit-mode-active', 'edit-mode-add', 'edit-mode-delete', 'edit-mode-move', 'edit-mode-select');
        }

        // Get config for current mode
        const config = ModeBannerConfig[currentMode];

        if (config) {
            // Show banner with appropriate content
            iconEl.textContent = config.icon;
            titleEl.textContent = config.title;

            // Dynamic description based on mode state
            let desc = config.desc;
            if (currentMode === EditMode.ADD_ITC) {
                desc = pendingFirstTub
                    ? 'Click second tubercle to complete the connection'
                    : 'Click first tubercle, then click second to connect';
            } else if (currentMode === EditMode.ADD_CHAIN && chainCurrentId !== null) {
                desc = `Selected: #${chainCurrentId}. Click to add connected tubercle or use arrow keys.`;
            }
            descEl.textContent = desc;

            banner.classList.add(config.colorClass);
            banner.style.display = 'flex';

            // Add glow to image container
            if (container) {
                const modeClass = 'edit-mode-' + config.colorClass.replace('mode-', '');
                container.classList.add('edit-mode-active');
                container.classList.add(modeClass);
            }
        } else {
            // Hide banner
            banner.style.display = 'none';
        }
    }

    /**
     * Update the toolbar mode badge
     */
    function updateToolbarBadge() {
        let badge = document.getElementById('toolbarModeBadge');
        const toolbar = document.querySelector('.image-toolbar');

        if (!toolbar) return;

        const config = ModeBannerConfig[currentMode];

        if (config) {
            // Create badge if it doesn't exist
            if (!badge) {
                badge = document.createElement('span');
                badge.id = 'toolbarModeBadge';
                badge.className = 'toolbar-mode-badge';
                badge.innerHTML = `
                    <span class="toolbar-mode-badge-text"></span>
                    <span class="toolbar-mode-badge-exit">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                        </svg>
                    </span>
                `;
                badge.addEventListener('click', () => setMode(EditMode.NONE));

                // Insert after filename
                const filename = document.getElementById('toolbarFilename');
                if (filename && filename.nextSibling) {
                    toolbar.insertBefore(badge, filename.nextSibling);
                } else {
                    toolbar.appendChild(badge);
                }
            }

            // Update badge content and style
            badge.classList.remove('mode-add', 'mode-delete', 'mode-move', 'mode-select');
            badge.classList.add(config.colorClass);
            badge.querySelector('.toolbar-mode-badge-text').textContent = config.title;
            badge.style.display = 'inline-flex';
        } else {
            // Hide badge
            if (badge) {
                badge.style.display = 'none';
            }
        }
    }

    /**
     * Update UI to reflect current mode
     */
    function updateModeUI() {
        // Update buttons
        const addTubBtn = document.getElementById('addTubBtn');
        const addItcBtn = document.getElementById('addItcBtn');
        const addChainBtn = document.getElementById('addChainBtn');
        const moveBtn = document.getElementById('moveBtn');
        const deleteMultipleTubBtn = document.getElementById('deleteMultipleTubBtn');
        const deleteMultipleItcBtn = document.getElementById('deleteMultipleItcBtn');
        const areaSelectBtn = document.getElementById('areaSelectBtn');

        if (addTubBtn) {
            addTubBtn.classList.toggle('active', currentMode === EditMode.ADD_TUB);
        }
        if (addItcBtn) {
            addItcBtn.classList.toggle('active', currentMode === EditMode.ADD_ITC);
        }
        if (addChainBtn) {
            addChainBtn.classList.toggle('active', currentMode === EditMode.ADD_CHAIN);
        }
        if (moveBtn) {
            moveBtn.classList.toggle('active', currentMode === EditMode.MOVE);
        }
        if (deleteMultipleTubBtn) {
            deleteMultipleTubBtn.classList.toggle('active', currentMode === EditMode.DELETE_MULTI_TUB);
        }
        if (deleteMultipleItcBtn) {
            deleteMultipleItcBtn.classList.toggle('active', currentMode === EditMode.DELETE_MULTI_ITC);
        }
        if (areaSelectBtn) {
            areaSelectBtn.classList.toggle('active', currentMode === EditMode.AREA_SELECT);
        }

        // Update status
        const statusEl = document.getElementById('editStatus');
        if (statusEl) {
            switch (currentMode) {
                case EditMode.ADD_TUB:
                    statusEl.textContent = 'Click on image to place tubercle';
                    break;
                case EditMode.ADD_ITC:
                    statusEl.textContent = pendingFirstTub
                        ? 'Click second tubercle to create connection'
                        : 'Click first tubercle';
                    break;
                case EditMode.ADD_CHAIN:
                    if (chainCurrentId === null) {
                        statusEl.textContent = 'Click to place or select first tubercle';
                    } else {
                        const parentId = chainParents[chainCurrentId];
                        statusEl.textContent = parentId !== undefined
                            ? `Selected: #${chainCurrentId} (parent: #${parentId})`
                            : `Selected: #${chainCurrentId} (root)`;
                    }
                    break;
                case EditMode.MOVE:
                    statusEl.textContent = 'Click destination to move selected tubercle';
                    break;
                case EditMode.DELETE_MULTI_TUB:
                    statusEl.textContent = 'Click tubercles to delete them';
                    break;
                case EditMode.DELETE_MULTI_ITC:
                    statusEl.textContent = 'Click connections to delete them';
                    break;
                case EditMode.AREA_SELECT:
                    statusEl.textContent = 'Click and drag to select an area. Release to select items.';
                    break;
                default:
                    statusEl.textContent = '';
            }
        }

        // Update the hint element at top of Edit tab
        const hintEl = document.getElementById('editModeHint');
        if (hintEl) {
            if (currentMode === EditMode.ADD_CHAIN) {
                hintEl.innerHTML = '<strong>Chain Mode:</strong> Click to add tubercle (auto-connects). Click existing to select. ' +
                    '<kbd>\u2191</kbd><kbd>\u2193</kbd> cycle neighbors, <kbd>\u2192</kbd> go to highlighted, <kbd>\u2190</kbd> go to parent. <kbd>Esc</kbd> finish.';
                hintEl.style.display = 'block';
            } else {
                hintEl.style.display = 'none';
            }
        }

        // Update mode banner and toolbar badge
        updateModeBanner();
        updateToolbarBadge();
    }

    /**
     * Update cursor based on mode
     * Uses data URI SVG cursors for cross-browser compatibility
     */
    function updateCursor() {
        const container = document.getElementById('imageContainer');
        if (!container) return;

        // Data URI SVG cursors - more reliable than file paths
        // Hotspot at center (12, 12) for 24x24 cursors
        const cursorSvgs = {
            // Add tubercle: circle with plus (blue)
            [EditMode.ADD_TUB]: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="white" stroke-width="2.5"/><circle cx="12" cy="12" r="9" fill="none" stroke="#3b82f6" stroke-width="1.5"/><line x1="12" y1="6" x2="12" y2="18" stroke="white" stroke-width="2.5"/><line x1="12" y1="6" x2="12" y2="18" stroke="#3b82f6" stroke-width="1.5"/><line x1="6" y1="12" x2="18" y2="12" stroke="white" stroke-width="2.5"/><line x1="6" y1="12" x2="18" y2="12" stroke="#3b82f6" stroke-width="1.5"/></svg>`,

            // Add connection: two circles with line (blue)
            [EditMode.ADD_ITC]: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><circle cx="6" cy="12" r="4" fill="none" stroke="white" stroke-width="2"/><circle cx="6" cy="12" r="4" fill="none" stroke="#3b82f6" stroke-width="1"/><circle cx="18" cy="12" r="4" fill="none" stroke="white" stroke-width="2"/><circle cx="18" cy="12" r="4" fill="none" stroke="#3b82f6" stroke-width="1"/><line x1="10" y1="12" x2="14" y2="12" stroke="white" stroke-width="2.5"/><line x1="10" y1="12" x2="14" y2="12" stroke="#3b82f6" stroke-width="1.5"/></svg>`,

            // Chain: three connected circles (blue)
            [EditMode.ADD_CHAIN]: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><circle cx="5" cy="12" r="3" fill="none" stroke="white" stroke-width="2"/><circle cx="5" cy="12" r="3" fill="none" stroke="#3b82f6" stroke-width="1"/><circle cx="12" cy="12" r="3" fill="none" stroke="white" stroke-width="2"/><circle cx="12" cy="12" r="3" fill="none" stroke="#3b82f6" stroke-width="1"/><circle cx="19" cy="12" r="3" fill="none" stroke="white" stroke-width="2"/><circle cx="19" cy="12" r="3" fill="none" stroke="#3b82f6" stroke-width="1"/><line x1="8" y1="12" x2="9" y2="12" stroke="white" stroke-width="2"/><line x1="8" y1="12" x2="9" y2="12" stroke="#3b82f6" stroke-width="1"/><line x1="15" y1="12" x2="16" y2="12" stroke="white" stroke-width="2"/><line x1="15" y1="12" x2="16" y2="12" stroke="#3b82f6" stroke-width="1"/></svg>`,

            // Move: four-way arrow (amber)
            [EditMode.MOVE]: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path d="M12 2 L15 6 L13 6 L13 11 L18 11 L18 9 L22 12 L18 15 L18 13 L13 13 L13 18 L15 18 L12 22 L9 18 L11 18 L11 13 L6 13 L6 15 L2 12 L6 9 L6 11 L11 11 L11 6 L9 6 Z" fill="#f59e0b" stroke="white" stroke-width="1"/></svg>`,

            // Delete tubercle: circle with X (red)
            [EditMode.DELETE_MULTI_TUB]: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="white" stroke-width="2.5"/><circle cx="12" cy="12" r="9" fill="none" stroke="#ef4444" stroke-width="1.5"/><line x1="8" y1="8" x2="16" y2="16" stroke="white" stroke-width="2.5"/><line x1="8" y1="8" x2="16" y2="16" stroke="#ef4444" stroke-width="1.5"/><line x1="16" y1="8" x2="8" y2="16" stroke="white" stroke-width="2.5"/><line x1="16" y1="8" x2="8" y2="16" stroke="#ef4444" stroke-width="1.5"/></svg>`,

            // Delete connection: line with X (red)
            [EditMode.DELETE_MULTI_ITC]: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><line x1="4" y1="12" x2="20" y2="12" stroke="white" stroke-width="3.5"/><line x1="4" y1="12" x2="20" y2="12" stroke="#ef4444" stroke-width="2"/><line x1="9" y1="7" x2="15" y2="17" stroke="white" stroke-width="2.5"/><line x1="9" y1="7" x2="15" y2="17" stroke="#ef4444" stroke-width="1.5"/><line x1="15" y1="7" x2="9" y2="17" stroke="white" stroke-width="2.5"/><line x1="15" y1="7" x2="9" y2="17" stroke="#ef4444" stroke-width="1.5"/></svg>`,

            // Area select: dashed rectangle (purple)
            [EditMode.AREA_SELECT]: `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" fill="none" stroke="white" stroke-width="2" stroke-dasharray="4,2"/><rect x="4" y="4" width="16" height="16" fill="none" stroke="#8b5cf6" stroke-width="1" stroke-dasharray="4,2"/><rect x="2" y="2" width="4" height="4" fill="white" stroke="#8b5cf6" stroke-width="1"/><rect x="18" y="2" width="4" height="4" fill="white" stroke="#8b5cf6" stroke-width="1"/><rect x="2" y="18" width="4" height="4" fill="white" stroke="#8b5cf6" stroke-width="1"/><rect x="18" y="18" width="4" height="4" fill="white" stroke="#8b5cf6" stroke-width="1"/></svg>`,
        };

        const fallbacks = {
            [EditMode.ADD_TUB]: 'crosshair',
            [EditMode.ADD_ITC]: 'pointer',
            [EditMode.ADD_CHAIN]: 'crosshair',
            [EditMode.MOVE]: 'move',
            [EditMode.DELETE_MULTI_TUB]: 'crosshair',
            [EditMode.DELETE_MULTI_ITC]: 'crosshair',
            [EditMode.AREA_SELECT]: 'crosshair',
        };

        const svg = cursorSvgs[currentMode];
        const fallback = fallbacks[currentMode];

        // Get all elements that need cursor styling
        const wrapper = document.getElementById('imageWrapper');
        const image = document.getElementById('mainImage');
        const canvas = document.getElementById('overlayCanvas');

        let cursorValue = '';
        if (svg) {
            // Encode the SVG for use in a data URI
            const encoded = encodeURIComponent(svg)
                .replace(/'/g, '%27')
                .replace(/"/g, '%22');
            cursorValue = `url("data:image/svg+xml,${encoded}") 12 12, ${fallback}`;
        }

        // Apply cursor to container and all child elements including canvas
        container.style.cursor = cursorValue;
        if (wrapper) wrapper.style.cursor = cursorValue;
        if (image) image.style.cursor = cursorValue;
        if (canvas) canvas.style.cursor = cursorValue;
    }

    /**
     * Handle click on the overlay canvas
     */
    async function handleCanvasClick(x, y) {
        try {
            switch (currentMode) {
                case EditMode.ADD_TUB:
                    await addTubercle(x, y);
                    break;
                case EditMode.ADD_ITC:
                    handleItcClick(x, y);
                    break;
                case EditMode.ADD_CHAIN:
                    await addTubercleToChain(x, y);
                    break;
                case EditMode.MOVE:
                    handleMoveClick(x, y);
                    break;
                case EditMode.DELETE_MULTI_TUB:
                    handleDeleteMultiTubClick(x, y);
                    break;
                case EditMode.DELETE_MULTI_ITC:
                    handleDeleteMultiItcClick(x, y);
                    break;
            }
        } catch (error) {
            console.error('Error handling canvas click:', error);
            window.app?.showToast(`Error: ${error.message}`, 'error');
        }
    }

    /**
     * Handle click for delete multiple tubercles mode
     */
    function handleDeleteMultiTubClick(x, y) {
        const clickedTub = findTubercleAt(x, y);
        if (clickedTub) {
            deleteTubercle(clickedTub.id, true); // Skip confirmation
        }
    }

    /**
     * Handle click for delete multiple connections mode
     */
    function handleDeleteMultiItcClick(x, y) {
        const clickedEdge = findEdgeAt(x, y);
        if (clickedEdge) {
            deleteEdge(clickedEdge, true); // Skip confirmation
        }
    }

    /**
     * Find edge at position
     */
    function findEdgeAt(x, y) {
        const clickThreshold = 10;
        let closestEdge = null;
        let closestDist = Infinity;

        edges.forEach(edge => {
            const dist = pointToLineDistance(x, y, edge.x1, edge.y1, edge.x2, edge.y2);
            if (dist < clickThreshold && dist < closestDist) {
                closestDist = dist;
                closestEdge = edge;
            }
        });

        return closestEdge;
    }

    /**
     * Distance from point to line segment
     */
    function pointToLineDistance(px, py, x1, y1, x2, y2) {
        const A = px - x1;
        const B = py - y1;
        const C = x2 - x1;
        const D = y2 - y1;

        const dot = A * C + B * D;
        const lenSq = C * C + D * D;
        let param = -1;

        if (lenSq !== 0) param = dot / lenSq;

        let xx, yy;

        if (param < 0) {
            xx = x1;
            yy = y1;
        } else if (param > 1) {
            xx = x2;
            yy = y2;
        } else {
            xx = x1 + param * C;
            yy = y1 + param * D;
        }

        const dx = px - xx;
        const dy = py - yy;
        return Math.sqrt(dx * dx + dy * dy);
    }

    /**
     * Add a new tubercle at position
     */
    async function addTubercle(x, y) {
        const calibration = getCalibration();
        const umPerPx = calibration?.um_per_px || 0.14;

        let effectiveRadius = getEffectiveDefaultRadius();
        let autoSized = false;
        let analysisResult = null;

        // Try auto-sizing if enabled
        if (autoSizeEnabled) {
            analysisResult = await analyzePointForSize(x, y);
            if (analysisResult) {
                effectiveRadius = analysisResult.radius_px;
                autoSized = true;
                // Phase 2: snap to detected center
                x = analysisResult.center_x;
                y = analysisResult.center_y;
            }
        }

        const newTub = {
            id: nextTubId++,
            centroid_x: x,
            centroid_y: y,
            radius_px: effectiveRadius,
            diameter_um: (effectiveRadius * 2) * umPerPx,
            circularity: autoSized && analysisResult?.circularity !== undefined
                ? analysisResult.circularity : 1.0,
        };

        // Add ellipse parameters if available from auto-sizing
        if (autoSized && analysisResult?.major_axis_px !== undefined) {
            newTub.major_axis_px = analysisResult.major_axis_px;
            newTub.minor_axis_px = analysisResult.minor_axis_px;
            newTub.major_axis_um = analysisResult.major_axis_um;
            newTub.minor_axis_um = analysisResult.minor_axis_um;
            newTub.orientation = analysisResult.orientation;
            newTub.eccentricity = analysisResult.eccentricity;
        }

        tubercles.push(newTub);

        // Push to undo stack
        window.undoManager?.push({
            type: window.undoManager.OperationType.ADD_TUB,
            data: { tub: { ...newTub } },
            redoData: { tub: { ...newTub } },
        });

        // Update displays
        refreshDisplays();
        markDirty();
        window.sets?.trackEdit('added_tubercles');
        logEdit('add_tub', { id: newTub.id, x: x.toFixed(1), y: y.toFixed(1), radius: effectiveRadius.toFixed(1), autoSized });

        // Update regenerate button state
        updateRegenerateButtonState();

        // Stay in add mode for multiple additions
        const sizeInfo = autoSized
            ? `auto-sized: ${newTub.diameter_um.toFixed(2)} µm`
            : `default: ${newTub.diameter_um.toFixed(2)} µm`;
        window.app?.showToast(`Added tubercle #${newTub.id} (${sizeInfo})`, 'success');
    }

    /**
     * Add a tubercle to the chain (with auto-connection to current)
     * Or select an existing tubercle if clicked on one
     */
    async function addTubercleToChain(x, y) {
        // Check if clicking on an existing tubercle
        const clickedTub = findTubercleAt(x, y);
        if (clickedTub) {
            // Select this tubercle - it becomes the current node
            chainCurrentId = clickedTub.id;
            // If not tracked yet, add as a root (no parent)
            if (chainParents[clickedTub.id] === undefined) {
                chainParents[clickedTub.id] = null; // null = root node
            }
            window.overlay?.selectTubercle(clickedTub.id);
            updateChainNeighbors();
            updateModeUI();
            window.app?.showToast(`Selected tubercle #${clickedTub.id}`, 'info');
            return;
        }

        const calibration = getCalibration();
        const umPerPx = calibration?.um_per_px || 0.14;

        let effectiveRadius = getEffectiveDefaultRadius();
        let autoSized = false;
        let analysisResult = null;

        // Try auto-sizing if enabled
        if (autoSizeEnabled) {
            analysisResult = await analyzePointForSize(x, y);
            if (analysisResult) {
                effectiveRadius = analysisResult.radius_px;
                autoSized = true;
                // Phase 2: snap to detected center
                x = analysisResult.center_x;
                y = analysisResult.center_y;
            }
        }

        const newTub = {
            id: nextTubId++,
            centroid_x: x,
            centroid_y: y,
            radius_px: effectiveRadius,
            diameter_um: (effectiveRadius * 2) * umPerPx,
            circularity: autoSized && analysisResult?.circularity !== undefined
                ? analysisResult.circularity : 1.0,
        };

        // Add ellipse parameters if available from auto-sizing
        if (autoSized && analysisResult?.major_axis_px !== undefined) {
            newTub.major_axis_px = analysisResult.major_axis_px;
            newTub.minor_axis_px = analysisResult.minor_axis_px;
            newTub.major_axis_um = analysisResult.major_axis_um;
            newTub.minor_axis_um = analysisResult.minor_axis_um;
            newTub.orientation = analysisResult.orientation;
            newTub.eccentricity = analysisResult.eccentricity;
        }

        tubercles.push(newTub);

        // Push tubercle to undo stack
        window.undoManager?.push({
            type: window.undoManager.OperationType.ADD_TUB,
            data: { tub: { ...newTub } },
            redoData: { tub: { ...newTub } },
        });

        // If there's a current tubercle, create connection from it
        if (chainCurrentId !== null) {
            const currentTub = tubercles.find(t => t.id === chainCurrentId);

            if (currentTub) {
                // Calculate distances
                const dx = newTub.centroid_x - currentTub.centroid_x;
                const dy = newTub.centroid_y - currentTub.centroid_y;
                const centerDistPx = Math.sqrt(dx * dx + dy * dy);
                const edgeDistPx = Math.max(0, centerDistPx - currentTub.radius_px - newTub.radius_px);

                const newEdge = {
                    id1: currentTub.id,
                    id2: newTub.id,
                    x1: currentTub.centroid_x,
                    y1: currentTub.centroid_y,
                    x2: newTub.centroid_x,
                    y2: newTub.centroid_y,
                    center_distance_um: centerDistPx * umPerPx,
                    edge_distance_um: edgeDistPx * umPerPx,
                };

                edges.push(newEdge);

                // Push edge to undo stack
                window.undoManager?.push({
                    type: window.undoManager.OperationType.ADD_ITC,
                    data: { edge: { ...newEdge } },
                    redoData: { edge: { ...newEdge } },
                });

                logEdit('add_itc', { id1: currentTub.id, id2: newTub.id });
            }
        }

        // Track parent relationship and update current
        chainParents[newTub.id] = chainCurrentId; // parent is the current node (or null if first)
        chainCurrentId = newTub.id;

        // Select the new tubercle
        window.overlay?.selectTubercle(newTub.id);

        // Update displays
        refreshDisplays();
        markDirty();
        window.sets?.trackEdit('added_tubercles');
        // Track connection if one was created
        if (chainParents[newTub.id] !== null) {
            window.sets?.trackEdit('added_connections');
        }
        updateChainNeighbors();
        updateModeUI();
        logEdit('add_tub', { id: newTub.id, x: x.toFixed(1), y: y.toFixed(1), radius: effectiveRadius.toFixed(1), chain: true, autoSized });

        // Update regenerate button state
        updateRegenerateButtonState();

        const sizeInfo = autoSized
            ? `auto-sized: ${newTub.diameter_um.toFixed(2)} µm`
            : `default: ${newTub.diameter_um.toFixed(2)} µm`;
        window.app?.showToast(`Added tubercle #${newTub.id} (${sizeInfo})`, 'success');
    }

    /**
     * Go to parent tubercle in the DAG (Left arrow)
     */
    function chainGoBack() {
        if (currentMode !== EditMode.ADD_CHAIN) return false;
        if (chainCurrentId === null) return false;

        const parentId = chainParents[chainCurrentId];
        if (parentId === null || parentId === undefined) {
            window.app?.showToast('Already at root (no parent)', 'info');
            return false;
        }

        chainCurrentId = parentId;
        window.overlay?.selectTubercle(parentId);

        updateChainNeighbors();
        updateModeUI();
        window.app?.showToast(`Moved to parent: tubercle #${parentId}`, 'info');
        return true;
    }

    /**
     * Go to highlighted neighbor (Right arrow)
     */
    function chainGoForward() {
        if (currentMode !== EditMode.ADD_CHAIN) return false;
        if (chainNeighborIndex < 0 || chainNeighborIndex >= chainNeighbors.length) {
            window.app?.showToast('No neighbor highlighted (use Up/Down)', 'info');
            return false;
        }

        const targetId = chainNeighbors[chainNeighborIndex];
        chainCurrentId = targetId;
        window.overlay?.selectTubercle(targetId);

        // Update neighbors for new position
        updateChainNeighbors();
        updateModeUI();

        window.app?.showToast(`Moved to tubercle #${targetId}`, 'info');
        return true;
    }

    /**
     * Update the list of neighbors for current tubercle
     */
    function updateChainNeighbors() {
        chainNeighbors = [];
        chainNeighborIndex = -1;

        if (chainCurrentId === null) {
            window.overlay?.setHighlightedEdge(null);
            return;
        }

        // Find all connected tubercles via edges
        edges.forEach(edge => {
            if (edge.id1 === chainCurrentId) {
                chainNeighbors.push(edge.id2);
            } else if (edge.id2 === chainCurrentId) {
                chainNeighbors.push(edge.id1);
            }
        });

        // If there are neighbors, highlight the first one (parent if exists)
        if (chainNeighbors.length > 0) {
            // Try to put parent first
            const parentId = chainParents[chainCurrentId];
            if (parentId !== null && parentId !== undefined) {
                const parentIndex = chainNeighbors.indexOf(parentId);
                if (parentIndex > 0) {
                    // Move parent to front
                    chainNeighbors.splice(parentIndex, 1);
                    chainNeighbors.unshift(parentId);
                }
            }
            chainNeighborIndex = 0;
            updateHighlightedEdge();
        } else {
            window.overlay?.setHighlightedEdge(null);
        }
    }

    /**
     * Update the highlighted edge in the overlay
     */
    function updateHighlightedEdge() {
        if (chainNeighborIndex < 0 || chainNeighborIndex >= chainNeighbors.length) {
            window.overlay?.setHighlightedEdge(null);
            return;
        }

        const neighborId = chainNeighbors[chainNeighborIndex];
        // Find the edge between current and neighbor
        const edge = edges.find(e =>
            (e.id1 === chainCurrentId && e.id2 === neighborId) ||
            (e.id1 === neighborId && e.id2 === chainCurrentId)
        );

        if (edge) {
            window.overlay?.setHighlightedEdge(edge);
        } else {
            window.overlay?.setHighlightedEdge(null);
        }
    }

    /**
     * Cycle to next neighbor (Down arrow)
     */
    function chainCycleNext() {
        if (currentMode !== EditMode.ADD_CHAIN) return false;
        if (chainNeighbors.length === 0) {
            window.app?.showToast('No neighbors to cycle through', 'info');
            return false;
        }

        chainNeighborIndex = (chainNeighborIndex + 1) % chainNeighbors.length;
        updateHighlightedEdge();

        const neighborId = chainNeighbors[chainNeighborIndex];
        const isParent = chainParents[chainCurrentId] === neighborId;
        window.app?.showToast(`Neighbor ${chainNeighborIndex + 1}/${chainNeighbors.length}: #${neighborId}${isParent ? ' (parent)' : ''}`, 'info');
        return true;
    }

    /**
     * Cycle to previous neighbor (Up arrow)
     */
    function chainCyclePrev() {
        if (currentMode !== EditMode.ADD_CHAIN) return false;
        if (chainNeighbors.length === 0) {
            window.app?.showToast('No neighbors to cycle through', 'info');
            return false;
        }

        chainNeighborIndex = (chainNeighborIndex - 1 + chainNeighbors.length) % chainNeighbors.length;
        updateHighlightedEdge();

        const neighborId = chainNeighbors[chainNeighborIndex];
        const isParent = chainParents[chainCurrentId] === neighborId;
        window.app?.showToast(`Neighbor ${chainNeighborIndex + 1}/${chainNeighbors.length}: #${neighborId}${isParent ? ' (parent)' : ''}`, 'info');
        return true;
    }

    /**
     * Handle click for ITC creation
     */
    function handleItcClick(x, y) {
        // Find clicked tubercle
        const clickedTub = findTubercleAt(x, y);

        if (!clickedTub) {
            window.app?.showToast('Click on a tubercle', 'info');
            return;
        }

        if (!pendingFirstTub) {
            // First click - select first tubercle
            pendingFirstTub = clickedTub;
            window.overlay?.selectTubercle(clickedTub.id);
            updateModeUI();
        } else {
            // Second click - create connection
            if (clickedTub.id === pendingFirstTub.id) {
                window.app?.showToast('Click a different tubercle', 'warning');
                return;
            }

            // Check if connection already exists
            const exists = edges.some(e =>
                (e.id1 === pendingFirstTub.id && e.id2 === clickedTub.id) ||
                (e.id1 === clickedTub.id && e.id2 === pendingFirstTub.id)
            );

            if (exists) {
                window.app?.showToast('Connection already exists', 'warning');
                pendingFirstTub = null;
                updateModeUI();
                return;
            }

            addConnection(pendingFirstTub, clickedTub);
            pendingFirstTub = null;
            updateModeUI();
        }
    }

    /**
     * Add a connection between two tubercles
     */
    function addConnection(tub1, tub2) {
        const calibration = getCalibration();
        const umPerPx = calibration?.um_per_px || 0.14;

        // Calculate distances
        const dx = tub2.centroid_x - tub1.centroid_x;
        const dy = tub2.centroid_y - tub1.centroid_y;
        const centerDistPx = Math.sqrt(dx * dx + dy * dy);
        const edgeDistPx = Math.max(0, centerDistPx - tub1.radius_px - tub2.radius_px);

        const newEdge = {
            id1: tub1.id,
            id2: tub2.id,
            x1: tub1.centroid_x,
            y1: tub1.centroid_y,
            x2: tub2.centroid_x,
            y2: tub2.centroid_y,
            center_distance_um: centerDistPx * umPerPx,
            edge_distance_um: edgeDistPx * umPerPx,
        };

        edges.push(newEdge);

        // Push to undo stack
        window.undoManager?.push({
            type: window.undoManager.OperationType.ADD_ITC,
            data: { edge: { ...newEdge } },
            redoData: { edge: { ...newEdge } },
        });

        // Update displays
        refreshDisplays();
        markDirty();
        window.sets?.trackEdit('added_connections');
        logEdit('add_itc', { id1: tub1.id, id2: tub2.id });

        window.app?.showToast(`Added connection ${tub1.id}-${tub2.id}`, 'success');
    }

    /**
     * Handle click for move operation
     */
    function handleMoveClick(x, y) {
        const selectedTub = window.overlay?.getSelectedTubercle();
        if (!selectedTub) {
            window.app?.showToast('Select a tubercle first', 'warning');
            return;
        }

        moveTubercle(selectedTub.id, x, y);
        // Stay in Move mode for moving multiple tubercles
    }

    /**
     * Move a tubercle to new position
     */
    function moveTubercle(id, newX, newY) {
        const tub = tubercles.find(t => t.id === id);
        if (!tub) return;

        const oldX = tub.centroid_x;
        const oldY = tub.centroid_y;

        // Push to undo stack before modifying
        window.undoManager?.push({
            type: window.undoManager.OperationType.MOVE_TUB,
            data: { id, oldX, oldY },
            redoData: { id, newX, newY },
        });

        // Update position
        tub.centroid_x = newX;
        tub.centroid_y = newY;

        // Update connected edges
        updateEdgesForTubercle(id);

        // Update displays
        refreshDisplays();
        markDirty();
        window.sets?.trackEdit('moved_tubercles');
        logEdit('move_tub', { id, from: `(${oldX.toFixed(1)}, ${oldY.toFixed(1)})`, to: `(${newX.toFixed(1)}, ${newY.toFixed(1)})` });
    }

    /**
     * Nudge selected tubercle by pixels
     */
    function nudgeSelected(dx, dy) {
        const selectedTub = window.overlay?.getSelectedTubercle();
        if (!selectedTub) return;

        const tub = tubercles.find(t => t.id === selectedTub.id);
        if (!tub) return;

        const oldX = tub.centroid_x;
        const oldY = tub.centroid_y;
        const newX = oldX + dx;
        const newY = oldY + dy;

        // Push to undo stack
        window.undoManager?.push({
            type: window.undoManager.OperationType.MOVE_TUB,
            data: { id: tub.id, oldX, oldY },
            redoData: { id: tub.id, newX, newY },
        });

        // Update position
        tub.centroid_x = newX;
        tub.centroid_y = newY;

        // Update connected edges
        updateEdgesForTubercle(tub.id);

        // Update displays
        refreshDisplays();
        markDirty();
        window.sets?.trackEdit('moved_tubercles');
    }

    /**
     * Resize selected tubercle
     */
    function resizeSelected(delta) {
        const selectedTub = window.overlay?.getSelectedTubercle();
        if (!selectedTub) return;

        const tub = tubercles.find(t => t.id === selectedTub.id);
        if (!tub) return;

        const oldRadius = tub.radius_px;
        const newRadius = Math.max(2, oldRadius + delta); // Minimum 2px radius

        // Push to undo stack
        window.undoManager?.push({
            type: window.undoManager.OperationType.RESIZE_TUB,
            data: { id: tub.id, oldRadius },
            redoData: { id: tub.id, newRadius },
        });

        // Update radius
        const calibration = getCalibration();
        const umPerPx = calibration?.um_per_px || 0.14;
        tub.radius_px = newRadius;
        tub.diameter_um = newRadius * 2 * umPerPx;

        // Update connected edges (edge distances change with radius)
        updateEdgesForTubercle(tub.id);

        // Update displays
        refreshDisplays();
        markDirty();
        window.sets?.trackEdit('resized_tubercles');
    }

    /**
     * Set radius for selected tubercle (from slider)
     */
    function setSelectedRadius(newRadius) {
        const selectedTub = window.overlay?.getSelectedTubercle();
        if (!selectedTub) return;

        const tub = tubercles.find(t => t.id === selectedTub.id);
        if (!tub) return;

        const oldRadius = tub.radius_px;
        if (Math.abs(newRadius - oldRadius) < 0.1) return; // No change

        // Push to undo stack
        window.undoManager?.push({
            type: window.undoManager.OperationType.RESIZE_TUB,
            data: { id: tub.id, oldRadius },
            redoData: { id: tub.id, newRadius },
        });

        // Update radius
        const calibration = getCalibration();
        const umPerPx = calibration?.um_per_px || 0.14;
        tub.radius_px = newRadius;
        tub.diameter_um = newRadius * 2 * umPerPx;

        // Update connected edges
        updateEdgesForTubercle(tub.id);

        // Update displays
        refreshDisplays();
        markDirty();
        window.sets?.trackEdit('resized_tubercles');
    }

    /**
     * Delete selected tubercle or edge
     */
    function deleteSelected() {
        const selectedTub = window.overlay?.getSelectedTubercle();
        const selectedEdge = window.overlay?.getSelectedEdge();

        if (selectedTub) {
            deleteTubercle(selectedTub.id);
        } else if (selectedEdge) {
            deleteEdge(selectedEdge);
        }
    }

    /**
     * Delete a tubercle by ID
     */
    function deleteTubercle(id, skipConfirm = false) {
        if (!allowDeleteWithoutConfirm && !skipConfirm) {
            showDeleteConfirmDialog(() => deleteTubercle(id, true));
            return;
        }

        const tubIndex = tubercles.findIndex(t => t.id === id);
        if (tubIndex === -1) return;

        const tub = tubercles[tubIndex];

        // Find connected edges
        const connectedEdges = edges.filter(e => e.id1 === id || e.id2 === id);
        const connectedEdgesCopy = connectedEdges.map(e => ({ ...e }));

        // Remove connected edges first
        connectedEdges.forEach(e => {
            const edgeIndex = edges.indexOf(e);
            if (edgeIndex !== -1) {
                edges.splice(edgeIndex, 1);
            }
        });

        // Remove tubercle
        tubercles.splice(tubIndex, 1);

        // Push to undo stack (includes connected edges for proper undo)
        window.undoManager?.push({
            type: window.undoManager.OperationType.DELETE_TUB,
            data: { tub: { ...tub }, connectedEdges: connectedEdgesCopy },
            redoData: { tubId: id },
        });

        // Clear selection
        window.overlay?.deselect();

        // Update displays
        refreshDisplays();
        markDirty();
        window.sets?.trackEdit('deleted_tubercles');
        // Also count deleted connections
        if (connectedEdgesCopy.length > 0) {
            window.sets?.trackEdit('deleted_connections', connectedEdgesCopy.length);
        }
        logEdit('delete_tub', { id });

        // Update regenerate button state
        updateRegenerateButtonState();

        window.app?.showToast(`Deleted tubercle #${id}`, 'success');
    }

    /**
     * Delete an edge
     */
    function deleteEdge(edge, skipConfirm = false) {
        if (!allowDeleteWithoutConfirm && !skipConfirm) {
            showDeleteConfirmDialog(() => deleteEdge(edge, true));
            return;
        }

        const edgeIndex = edges.findIndex(e =>
            e.id1 === edge.id1 && e.id2 === edge.id2
        );
        if (edgeIndex === -1) return;

        const edgeCopy = { ...edges[edgeIndex] };
        edges.splice(edgeIndex, 1);

        // Push to undo stack
        window.undoManager?.push({
            type: window.undoManager.OperationType.DELETE_ITC,
            data: { edge: edgeCopy },
            redoData: { id1: edge.id1, id2: edge.id2 },
        });

        // Clear selection
        window.overlay?.deselect();

        // Update displays
        refreshDisplays();
        markDirty();
        window.sets?.trackEdit('deleted_connections');
        logEdit('delete_itc', { id1: edge.id1, id2: edge.id2 });

        window.app?.showToast(`Deleted connection ${edge.id1}-${edge.id2}`, 'success');
    }

    /**
     * Regenerate all connections using the specified graph type
     */
    async function regenerateConnections() {
        // Check calibration
        const calibration = getCalibration();
        if (!calibration || !calibration.um_per_px) {
            window.app?.showToast('Please set calibration first', 'warning');
            return;
        }

        // Need at least 2 tubercles
        if (tubercles.length < 2) {
            window.app?.showToast('Need at least 2 tubercles to generate connections', 'warning');
            return;
        }

        // Get graph type from Edit tab dropdown
        const graphTypeSelect = document.getElementById('editGraphType');
        const graphType = graphTypeSelect?.value || 'gabriel';

        // Get culling params from Configure tab
        const params = window.configure?.getParams() || {};
        const cullLongEdges = params.cull_long_edges !== undefined ? params.cull_long_edges : true;
        const cullFactor = params.cull_factor || 1.8;

        // Store old edges for undo
        const oldEdges = edges.map(e => ({ ...e }));

        try {
            const response = await fetch('/api/regenerate-connections', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tubercles: tubercles,
                    graph_type: graphType,
                    cull_long_edges: cullLongEdges,
                    cull_factor: cullFactor,
                }),
            });

            const result = await response.json();

            if (result.error) {
                window.app?.showToast(result.error, 'error');
                return;
            }

            // Update edges
            edges = result.edges || [];

            // Update tubercles with boundary flags if provided
            if (result.tubercles) {
                const boundaryMap = new Map();
                result.tubercles.forEach(t => {
                    boundaryMap.set(t.id, t.is_boundary);
                });
                tubercles.forEach(t => {
                    if (boundaryMap.has(t.id)) {
                        t.is_boundary = boundaryMap.get(t.id);
                    }
                });
            }

            // Push to undo stack
            window.undoManager?.push({
                type: window.undoManager.OperationType.REGENERATE_CONNECTIONS,
                data: { oldEdges: oldEdges, graphType: graphType },
                redoData: { newEdges: edges.map(e => ({ ...e })), graphType: graphType },
            });

            // Update displays
            refreshDisplays();
            markDirty();
            window.sets?.trackEdit('regenerate_connections');
            logEdit('regenerate_connections', { graph_type: graphType, n_edges: edges.length });

            // Record history event
            window.sets?.addHistoryEvent('auto_connect', {
                graph_type: graphType,
                n_tubercles: tubercles.length,
                n_edges: edges.length,
                cull_long_edges: cullLongEdges,
                cull_factor: cullFactor,
                calibration_um_per_pixel: calibration?.um_per_px,
            });

            window.app?.showToast(
                `Regenerated ${edges.length} connections using ${graphType}`,
                'success'
            );

        } catch (err) {
            console.error('Connection regeneration failed:', err);
            window.app?.showToast('Connection regeneration failed: ' + err.message, 'error');
        }
    }

    /**
     * Show delete confirmation dialog
     */
    function showDeleteConfirmDialog(onConfirm) {
        window.app?.showModal(
            'Confirm Delete',
            '<p>Are you sure you want to delete this item?</p>',
            [
                { text: 'Cancel', action: () => {} },
                { text: 'Delete', primary: true, action: onConfirm },
            ]
        );
    }

    /**
     * Find tubercle at position
     */
    function findTubercleAt(x, y) {
        let closest = null;
        let closestDist = Infinity;

        tubercles.forEach(tub => {
            const dx = x - tub.centroid_x;
            const dy = y - tub.centroid_y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            // Click within radius * 1.5 for easier selection
            if (dist < tub.radius_px * 1.5 && dist < closestDist) {
                closestDist = dist;
                closest = tub;
            }
        });

        return closest;
    }

    /**
     * Update edges connected to a tubercle
     */
    function updateEdgesForTubercle(tubId) {
        const tub = tubercles.find(t => t.id === tubId);
        if (!tub) return;

        const calibration = getCalibration();
        const umPerPx = calibration?.um_per_px || 0.14;

        edges.forEach(edge => {
            if (edge.id1 === tubId) {
                edge.x1 = tub.centroid_x;
                edge.y1 = tub.centroid_y;
            } else if (edge.id2 === tubId) {
                edge.x2 = tub.centroid_x;
                edge.y2 = tub.centroid_y;
            } else {
                return;
            }

            // Recalculate distances
            const tub1 = tubercles.find(t => t.id === edge.id1);
            const tub2 = tubercles.find(t => t.id === edge.id2);
            if (tub1 && tub2) {
                const dx = tub2.centroid_x - tub1.centroid_x;
                const dy = tub2.centroid_y - tub1.centroid_y;
                const centerDistPx = Math.sqrt(dx * dx + dy * dy);
                const edgeDistPx = Math.max(0, centerDistPx - tub1.radius_px - tub2.radius_px);

                edge.center_distance_um = centerDistPx * umPerPx;
                edge.edge_distance_um = edgeDistPx * umPerPx;
            }
        });
    }

    /**
     * Refresh all displays with current data
     */
    async function refreshDisplays() {
        // Update overlay
        window.overlay?.setData(tubercles, edges);

        // Update data tables
        const stats = await calculateStatistics();
        window.data?.setData(tubercles, edges, stats);
    }

    /**
     * Calculate statistics from current data (async - fetches hexagonalness from server)
     */
    async function calculateStatistics() {
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
                const variance = diameters.reduce((sum, d) => sum + Math.pow(d - mean_diameter_um, 2), 0) / (n_tubercles - 1);
                std_diameter_um = Math.sqrt(variance);
            }
        }

        if (n_edges > 0) {
            const spaces = edges.map(e => e.edge_distance_um);
            mean_space_um = spaces.reduce((a, b) => a + b, 0) / n_edges;
            if (n_edges > 1) {
                const variance = spaces.reduce((sum, s) => sum + Math.pow(s - mean_space_um, 2), 0) / (n_edges - 1);
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
            degree_histogram: {},
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

    /**
     * Mark data as dirty (unsaved changes)
     */
    function markDirty() {
        // Mark the current set as dirty in the sets module
        window.sets?.markDirty();

        // Sync data to sets module
        window.sets?.setCurrentData(tubercles, edges);

        // The extraction module tracks dirty state
        // We need to manually trigger it
        const indicator = document.getElementById('unsavedIndicator');
        if (indicator) indicator.style.display = 'inline-block';

        const indicatorImage = document.getElementById('unsavedIndicatorImage');
        if (indicatorImage) indicatorImage.style.display = 'inline-block';

        const saveBtn = document.getElementById('saveSloBtn');
        if (saveBtn) saveBtn.classList.add('has-changes');

        // Notify extraction module
        document.dispatchEvent(new CustomEvent('dataModified'));

        // Recalculate boundaries (debounced)
        recalculateBoundariesDebounced();
    }

    // Debounce timer for boundary recalculation
    let boundaryRecalcTimer = null;

    /**
     * Debounced boundary recalculation - waits 300ms after last edit
     */
    function recalculateBoundariesDebounced() {
        if (boundaryRecalcTimer) {
            clearTimeout(boundaryRecalcTimer);
        }
        boundaryRecalcTimer = setTimeout(recalculateBoundaries, 300);
    }

    /**
     * Recalculate boundary status for all tubercles
     */
    async function recalculateBoundaries() {
        if (tubercles.length < 3) {
            // All nodes are boundary if less than 3
            tubercles.forEach(t => { t.is_boundary = true; });
            refreshDisplays();
            return;
        }

        try {
            const response = await fetch('/api/recalculate-boundaries', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ tubercles }),
            });

            const result = await response.json();

            if (result.success && result.tubercles) {
                // Update boundary flags in our local tubercles array
                const boundaryMap = new Map();
                result.tubercles.forEach(t => {
                    boundaryMap.set(t.id, t.is_boundary);
                });

                tubercles.forEach(t => {
                    if (boundaryMap.has(t.id)) {
                        t.is_boundary = boundaryMap.get(t.id);
                    }
                });

                // Sync updated data
                window.sets?.setCurrentData(tubercles, edges);

                // Refresh all displays
                refreshDisplays();

                // Update statistics with boundary counts
                if (window.data) {
                    const stats = await calculateStatistics();
                    stats.n_boundary = result.n_boundary;
                    stats.n_interior = result.n_interior;
                    window.data.setData(tubercles, edges, stats);
                }
            }
        } catch (err) {
            console.error('Failed to recalculate boundaries:', err);
        }
    }

    /**
     * Log an edit operation
     */
    function logEdit(type, details) {
        fetch('/api/log', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                event_type: 'edit_' + type,
                details,
            }),
        }).catch(err => console.error('Failed to log edit:', err));

        // Refresh log display
        window.app?.loadLog();
    }

    /**
     * Handle undo operation
     */
    function handleUndo(operation) {
        const { type, data } = operation;

        switch (type) {
            case window.undoManager.OperationType.ADD_TUB: {
                // Remove the added tubercle
                const idx = tubercles.findIndex(t => t.id === data.tub.id);
                if (idx !== -1) tubercles.splice(idx, 1);
                break;
            }
            case window.undoManager.OperationType.DELETE_TUB: {
                // Restore the deleted tubercle and its connections
                tubercles.push({ ...data.tub });
                data.connectedEdges.forEach(e => edges.push({ ...e }));
                break;
            }
            case window.undoManager.OperationType.MOVE_TUB: {
                // Restore old position
                const tub = tubercles.find(t => t.id === data.id);
                if (tub) {
                    tub.centroid_x = data.oldX;
                    tub.centroid_y = data.oldY;
                    updateEdgesForTubercle(data.id);
                }
                break;
            }
            case window.undoManager.OperationType.RESIZE_TUB: {
                // Restore old radius
                const tub = tubercles.find(t => t.id === data.id);
                if (tub) {
                    const calibration = getCalibration();
                    const umPerPx = calibration?.um_per_px || 0.14;
                    tub.radius_px = data.oldRadius;
                    tub.diameter_um = data.oldRadius * 2 * umPerPx;
                    updateEdgesForTubercle(data.id);
                }
                break;
            }
            case window.undoManager.OperationType.ADD_ITC: {
                // Remove the added edge
                const idx = edges.findIndex(e =>
                    e.id1 === data.edge.id1 && e.id2 === data.edge.id2
                );
                if (idx !== -1) edges.splice(idx, 1);
                break;
            }
            case window.undoManager.OperationType.DELETE_ITC: {
                // Restore the deleted edge
                edges.push({ ...data.edge });
                break;
            }
            case window.undoManager.OperationType.DELETE_MULTI: {
                // Restore all deleted tubercles
                data.tubs.forEach(t => {
                    tubercles.push({ ...t });
                });
                // Restore all deleted edges
                data.edges.forEach(e => {
                    edges.push({ ...e });
                });
                // Update next ID if needed
                if (data.tubs.length > 0) {
                    const maxId = Math.max(...data.tubs.map(t => t.id));
                    if (maxId >= nextTubId) {
                        nextTubId = maxId + 1;
                    }
                }
                break;
            }
            case window.undoManager.OperationType.REGENERATE_CONNECTIONS: {
                // Restore old edges
                edges = data.oldEdges.map(e => ({ ...e }));
                break;
            }
        }

        refreshDisplays();
        markDirty();
        updateRegenerateButtonState();
    }

    /**
     * Handle redo operation
     */
    function handleRedo(operation) {
        const { type, redoData } = operation;

        switch (type) {
            case window.undoManager.OperationType.ADD_TUB: {
                // Re-add the tubercle
                tubercles.push({ ...redoData.tub });
                break;
            }
            case window.undoManager.OperationType.DELETE_TUB: {
                // Re-delete the tubercle
                const idx = tubercles.findIndex(t => t.id === redoData.tubId);
                if (idx !== -1) {
                    // Also remove connected edges
                    edges = edges.filter(e => e.id1 !== redoData.tubId && e.id2 !== redoData.tubId);
                    tubercles.splice(idx, 1);
                }
                break;
            }
            case window.undoManager.OperationType.MOVE_TUB: {
                // Apply new position
                const tub = tubercles.find(t => t.id === redoData.id);
                if (tub) {
                    tub.centroid_x = redoData.newX;
                    tub.centroid_y = redoData.newY;
                    updateEdgesForTubercle(redoData.id);
                }
                break;
            }
            case window.undoManager.OperationType.RESIZE_TUB: {
                // Apply new radius
                const tub = tubercles.find(t => t.id === redoData.id);
                if (tub) {
                    const calibration = getCalibration();
                    const umPerPx = calibration?.um_per_px || 0.14;
                    tub.radius_px = redoData.newRadius;
                    tub.diameter_um = redoData.newRadius * 2 * umPerPx;
                    updateEdgesForTubercle(redoData.id);
                }
                break;
            }
            case window.undoManager.OperationType.ADD_ITC: {
                // Re-add the edge
                edges.push({ ...redoData.edge });
                break;
            }
            case window.undoManager.OperationType.DELETE_ITC: {
                // Re-delete the edge
                const idx = edges.findIndex(e =>
                    e.id1 === redoData.id1 && e.id2 === redoData.id2
                );
                if (idx !== -1) edges.splice(idx, 1);
                break;
            }
            case window.undoManager.OperationType.DELETE_MULTI: {
                // Re-delete all tubercles
                redoData.tubIds.forEach(id => {
                    const idx = tubercles.findIndex(t => t.id === id);
                    if (idx !== -1) tubercles.splice(idx, 1);
                });
                // Re-delete all edges (filter by key)
                const edgeKeysToDelete = new Set(redoData.edgeKeys);
                edges = edges.filter(e => {
                    const key = `${e.id1}-${e.id2}`;
                    return !edgeKeysToDelete.has(key);
                });
                break;
            }
            case window.undoManager.OperationType.REGENERATE_CONNECTIONS: {
                // Re-apply the new edges
                edges = redoData.newEdges.map(e => ({ ...e }));
                break;
            }
        }

        refreshDisplays();
        markDirty();
        updateRegenerateButtonState();
    }

    /**
     * Cycle through selection (Tab key)
     */
    function cycleSelection() {
        // Get all items
        const allItems = [];

        if (areTubesVisible()) {
            tubercles.forEach(t => allItems.push({ type: 'tub', item: t }));
        }
        if (areLinksVisible()) {
            edges.forEach((e, idx) => allItems.push({ type: 'edge', item: e, idx }));
        }

        if (allItems.length === 0) return;

        // Find current selection
        const selectedTub = window.overlay?.getSelectedTubercle();
        const selectedEdge = window.overlay?.getSelectedEdge();

        let currentIdx = -1;
        if (selectedTub) {
            currentIdx = allItems.findIndex(item =>
                item.type === 'tub' && item.item.id === selectedTub.id
            );
        } else if (selectedEdge) {
            currentIdx = allItems.findIndex(item =>
                item.type === 'edge' &&
                item.item.id1 === selectedEdge.id1 &&
                item.item.id2 === selectedEdge.id2
            );
        }

        // Move to next item
        const nextIdx = (currentIdx + 1) % allItems.length;
        const nextItem = allItems[nextIdx];

        if (nextItem.type === 'tub') {
            window.overlay?.selectTubercle(nextItem.item.id);
        } else {
            window.overlay?.selectEdge(nextItem.idx);
        }
    }

    /**
     * Set allow delete without confirmation
     */
    function setAllowDeleteWithoutConfirm(value) {
        allowDeleteWithoutConfirm = value;
    }

    /**
     * Delete all multi-selected items
     */
    function deleteMultiSelected() {
        const selectedTubs = window.overlay?.getMultiSelectedTubercles() || [];
        const selectedEdges = window.overlay?.getMultiSelectedEdges() || [];

        if (selectedTubs.length === 0 && selectedEdges.length === 0) {
            window.app?.showToast('No items selected', 'info');
            return;
        }

        // Confirmation dialog
        const msg = `Delete ${selectedTubs.length} tubercle(s) and ${selectedEdges.length} connection(s)?`;
        if (!allowDeleteWithoutConfirm && !confirm(msg)) {
            return;
        }

        // Perform batch delete
        batchDelete(selectedTubs, selectedEdges);
    }

    /**
     * Batch delete tubercles and edges with single undo operation
     */
    function batchDelete(tubs, selectedEdges) {
        // Collect all data for undo
        const deletedTubs = tubs.map(t => ({ ...t }));
        const deletedEdges = [];
        const orphanedEdges = [];

        // Find all edges that will be orphaned (connected to deleted tubs)
        const tubIdsToDelete = new Set(tubs.map(t => t.id));
        edges.forEach(e => {
            if (tubIdsToDelete.has(e.id1) || tubIdsToDelete.has(e.id2)) {
                orphanedEdges.push({ ...e });
            }
        });

        // Combine explicitly selected edges with orphaned edges (deduped)
        const edgeKeySet = new Set();
        [...selectedEdges, ...orphanedEdges].forEach(e => {
            const key = `${e.id1}-${e.id2}`;
            if (!edgeKeySet.has(key)) {
                edgeKeySet.add(key);
                deletedEdges.push({ ...e });
            }
        });

        // Remove tubercles
        tubs.forEach(t => {
            const idx = tubercles.findIndex(tb => tb.id === t.id);
            if (idx !== -1) tubercles.splice(idx, 1);
        });

        // Remove all edges that should be deleted
        const edgeKeysToDelete = new Set(deletedEdges.map(e => `${e.id1}-${e.id2}`));
        edges = edges.filter(e => !edgeKeysToDelete.has(`${e.id1}-${e.id2}`));

        // Push single undo operation
        window.undoManager?.push({
            type: window.undoManager.OperationType.DELETE_MULTI,
            data: { tubs: deletedTubs, edges: deletedEdges },
            redoData: {
                tubIds: deletedTubs.map(t => t.id),
                edgeKeys: deletedEdges.map(e => `${e.id1}-${e.id2}`)
            }
        });

        // Clear multi-selection
        window.overlay?.clearMultiSelection();

        // Clear single selection too
        window.overlay?.deselect();

        // Update displays
        refreshDisplays();
        markDirty();
        // Track edits
        if (deletedTubs.length > 0) {
            window.sets?.trackEdit('deleted_tubercles', deletedTubs.length);
        }
        if (deletedEdges.length > 0) {
            window.sets?.trackEdit('deleted_connections', deletedEdges.length);
        }
        logEdit('delete_multi', {
            tubCount: deletedTubs.length,
            edgeCount: deletedEdges.length
        });

        // Update regenerate button state
        updateRegenerateButtonState();

        window.app?.showToast(
            `Deleted ${deletedTubs.length} tubercle(s) and ${deletedEdges.length} connection(s)`,
            'success'
        );
    }

    /**
     * Clear all tubercles and edges from the current set
     */
    function clearAll() {
        // Check if there's anything to clear
        if (tubercles.length === 0 && edges.length === 0) {
            window.app?.showToast('Nothing to clear', 'info');
            return;
        }

        // Show confirmation dialog
        const tubCount = tubercles.length;
        const edgeCount = edges.length;
        const confirmed = confirm(
            `Are you sure you want to delete ALL data from the current set?\n\n` +
            `This will delete:\n` +
            `  - ${tubCount} tubercle(s)\n` +
            `  - ${edgeCount} connection(s)\n\n` +
            `This action can be undone with Ctrl+Z.`
        );

        if (!confirmed) return;

        // Save copies for undo
        const deletedTubs = tubercles.map(t => ({ ...t }));
        const deletedEdges = edges.map(e => ({ ...e }));

        // Clear arrays
        tubercles.length = 0;
        edges.length = 0;

        // Push single undo operation
        window.undoManager?.push({
            type: window.undoManager.OperationType.DELETE_MULTI,
            data: { tubs: deletedTubs, edges: deletedEdges },
            redoData: {
                tubIds: deletedTubs.map(t => t.id),
                edgeKeys: deletedEdges.map(e => `${e.id1}-${e.id2}`)
            }
        });

        // Clear any selections
        window.overlay?.clearMultiSelection();
        window.overlay?.deselect();

        // Update displays
        refreshDisplays();
        markDirty();

        // Track edits
        if (deletedTubs.length > 0) {
            window.sets?.trackEdit('deleted_tubercles', deletedTubs.length);
        }
        if (deletedEdges.length > 0) {
            window.sets?.trackEdit('deleted_connections', deletedEdges.length);
        }
        logEdit('clear_all', {
            tubCount: deletedTubs.length,
            edgeCount: deletedEdges.length
        });

        // Update regenerate button state
        updateRegenerateButtonState();

        window.app?.showToast(
            `Cleared ${deletedTubs.length} tubercle(s) and ${deletedEdges.length} connection(s)`,
            'success'
        );
    }

    // ========================================
    // Area Selection Mouse Handling
    // ========================================

    let areaSelectMouseHandlersBound = false;

    /**
     * Setup mouse handlers for area selection
     */
    function setupAreaSelectMouseHandlers() {
        if (areaSelectMouseHandlersBound) return;

        const canvas = window.overlay?.getCanvas();
        if (!canvas) return;

        canvas.addEventListener('mousedown', handleAreaSelectMouseDown);
        canvas.addEventListener('mousemove', handleAreaSelectMouseMove);
        canvas.addEventListener('mouseup', handleAreaSelectMouseUp);

        areaSelectMouseHandlersBound = true;
    }

    function handleAreaSelectMouseDown(e) {
        if (currentMode !== EditMode.AREA_SELECT) return;
        if (e.button !== 0) return; // Only left click

        const coords = window.overlay.clientToImageCoords(e.clientX, e.clientY);
        window.overlay.startAreaSelect(coords.x, coords.y);
        e.preventDefault();
    }

    function handleAreaSelectMouseMove(e) {
        if (currentMode !== EditMode.AREA_SELECT) return;
        if (!window.overlay.isInAreaSelectMode()) return;

        const coords = window.overlay.clientToImageCoords(e.clientX, e.clientY);
        window.overlay.updateAreaSelect(coords.x, coords.y);
    }

    function handleAreaSelectMouseUp(e) {
        if (currentMode !== EditMode.AREA_SELECT) return;
        if (!window.overlay.isInAreaSelectMode()) return;

        const coords = window.overlay.clientToImageCoords(e.clientX, e.clientY);
        window.overlay.updateAreaSelect(coords.x, coords.y);
        const selected = window.overlay.finishAreaSelect();

        // Select items within rectangle
        if (selected.tubIds.length > 0 || selected.edgeIdxs.length > 0) {
            window.overlay.selectMultipleTubercles(selected.tubIds);
            window.overlay.addToMultiSelection(null, selected.edgeIdxs);

            window.app?.showToast(
                `Selected ${selected.tubIds.length} tubercle(s) and ${selected.edgeIdxs.length} connection(s)`,
                'info'
            );
        } else {
            window.app?.showToast('No items in selection area', 'info');
        }
    }

    /**
     * Enter area select mode
     */
    function enterAreaSelectMode() {
        setMode(EditMode.AREA_SELECT);
        setupAreaSelectMouseHandlers();
    }

    /**
     * Exit area select mode
     */
    function exitAreaSelectMode() {
        window.overlay?.cancelAreaSelect();
        setMode(EditMode.NONE);
    }

    /**
     * Update delete multiple buttons enabled state
     */
    function updateDeleteMultipleButtons(enabled) {
        const deleteMultipleTubBtn = document.getElementById('deleteMultipleTubBtn');
        const deleteMultipleItcBtn = document.getElementById('deleteMultipleItcBtn');

        if (deleteMultipleTubBtn) {
            deleteMultipleTubBtn.disabled = !enabled;
            if (!enabled && currentMode === EditMode.DELETE_MULTI_TUB) {
                setMode(EditMode.NONE);
            }
        }
        if (deleteMultipleItcBtn) {
            deleteMultipleItcBtn.disabled = !enabled;
            if (!enabled && currentMode === EditMode.DELETE_MULTI_ITC) {
                setMode(EditMode.NONE);
            }
        }
    }

    /**
     * Initialize
     */
    function init() {
        // Listen for undo/redo events
        document.addEventListener('undoOperation', (e) => {
            handleUndo(e.detail.operation);
        });

        document.addEventListener('redoOperation', (e) => {
            handleRedo(e.detail.operation);
        });

        // Listen for data changes from extraction
        document.addEventListener('extractionComplete', (e) => {
            if (e.detail) {
                setData(e.detail.tubercles, e.detail.edges);
            }
        });

        // Banner exit button
        const bannerExitBtn = document.getElementById('editModeBannerExit');
        if (bannerExitBtn) {
            bannerExitBtn.addEventListener('click', () => {
                setMode(EditMode.NONE);
            });
        }

        // Initialize buttons
        const addTubBtn = document.getElementById('addTubBtn');
        if (addTubBtn) {
            addTubBtn.addEventListener('click', () => {
                if (currentMode === EditMode.ADD_TUB) {
                    setMode(EditMode.NONE);
                } else {
                    setMode(EditMode.ADD_TUB);
                }
            });
        }

        const addItcBtn = document.getElementById('addItcBtn');
        if (addItcBtn) {
            addItcBtn.addEventListener('click', () => {
                if (currentMode === EditMode.ADD_ITC) {
                    setMode(EditMode.NONE);
                } else {
                    setMode(EditMode.ADD_ITC);
                }
            });
        }

        const addChainBtn = document.getElementById('addChainBtn');
        if (addChainBtn) {
            addChainBtn.addEventListener('click', () => {
                if (currentMode === EditMode.ADD_CHAIN) {
                    setMode(EditMode.NONE);
                } else {
                    setMode(EditMode.ADD_CHAIN);
                }
            });
        }

        // Default tubercle diameter input
        const defaultDiameterInput = document.getElementById('defaultTubercleDiameter');
        if (defaultDiameterInput) {
            defaultDiameterInput.addEventListener('change', (e) => {
                const val = e.target.value.trim();
                if (val === '') {
                    setDefaultDiameterUm(null);
                } else {
                    const num = parseFloat(val);
                    if (!isNaN(num) && num > 0) {
                        setDefaultDiameterUm(num);
                    }
                }
                // Mark as dirty since per-image setting changed
                markDirty();
            });
            // Also handle input event for immediate feedback
            defaultDiameterInput.addEventListener('input', () => {
                updateDefaultDiameterHint();
            });
        }

        // Listen for calibration changes to update hints
        document.addEventListener('calibrationChanged', () => {
            updateDefaultDiameterHint();
            updateAutoSizeHint();
        });

        // Auto-size checkbox
        const autoSizeCheckbox = document.getElementById('autoSizeEnabled');
        if (autoSizeCheckbox) {
            // Initialize from settings
            const savedAutoSize = window.settings?.get('editor.autoSizeEnabled');
            if (savedAutoSize !== undefined) {
                autoSizeEnabled = savedAutoSize;
                autoSizeCheckbox.checked = autoSizeEnabled;
            }
            updateAutoSizeHint();

            autoSizeCheckbox.addEventListener('change', (e) => {
                setAutoSizeEnabled(e.target.checked);
            });
        }

        // Auto-size region factor slider
        const regionFactorSlider = document.getElementById('autoSizeRegionFactor');
        const regionFactorValue = document.getElementById('autoSizeRegionFactorValue');
        if (regionFactorSlider) {
            // Initialize from settings
            const savedFactor = window.settings?.get('editor.autoSizeRegionFactor');
            if (savedFactor !== undefined) {
                autoSizeRegionFactor = savedFactor;
                regionFactorSlider.value = savedFactor;
            }
            if (regionFactorValue) {
                regionFactorValue.textContent = `${regionFactorSlider.value}x`;
            }

            regionFactorSlider.addEventListener('input', (e) => {
                const factor = parseInt(e.target.value);
                autoSizeRegionFactor = factor;
                if (regionFactorValue) {
                    regionFactorValue.textContent = `${factor}x`;
                }
                window.settings?.set('editor.autoSizeRegionFactor', factor);
            });
        }

        // Auto-size show region checkbox
        const showRegionCheckbox = document.getElementById('autoSizeShowRegion');
        if (showRegionCheckbox) {
            // Initialize from settings
            const savedShowRegion = window.settings?.get('editor.autoSizeShowRegion');
            if (savedShowRegion !== undefined) {
                autoSizeShowRegion = savedShowRegion;
                showRegionCheckbox.checked = autoSizeShowRegion;
            }

            showRegionCheckbox.addEventListener('change', (e) => {
                autoSizeShowRegion = e.target.checked;
                window.settings?.set('editor.autoSizeShowRegion', e.target.checked);
            });
        }

        const moveBtn = document.getElementById('moveBtn');
        if (moveBtn) {
            moveBtn.addEventListener('click', () => {
                if (currentMode === EditMode.MOVE) {
                    setMode(EditMode.NONE);
                } else {
                    if (!window.overlay?.getSelectedTubercle()) {
                        window.app?.showToast('Select a tubercle first', 'warning');
                        return;
                    }
                    setMode(EditMode.MOVE);
                }
            });
        }

        const deleteTubBtn = document.getElementById('deleteTubBtn');
        if (deleteTubBtn) {
            deleteTubBtn.addEventListener('click', () => {
                const selectedTub = window.overlay?.getSelectedTubercle();
                if (selectedTub) {
                    deleteTubercle(selectedTub.id);
                }
            });
        }

        const deleteItcBtn = document.getElementById('deleteItcBtn');
        if (deleteItcBtn) {
            deleteItcBtn.addEventListener('click', () => {
                const selectedEdge = window.overlay?.getSelectedEdge();
                if (selectedEdge) {
                    deleteEdge(selectedEdge);
                }
            });
        }

        const deleteMultipleTubBtn = document.getElementById('deleteMultipleTubBtn');
        if (deleteMultipleTubBtn) {
            deleteMultipleTubBtn.addEventListener('click', () => {
                if (currentMode === EditMode.DELETE_MULTI_TUB) {
                    setMode(EditMode.NONE);
                } else {
                    setMode(EditMode.DELETE_MULTI_TUB);
                }
            });
        }

        const deleteMultipleItcBtn = document.getElementById('deleteMultipleItcBtn');
        if (deleteMultipleItcBtn) {
            deleteMultipleItcBtn.addEventListener('click', () => {
                if (currentMode === EditMode.DELETE_MULTI_ITC) {
                    setMode(EditMode.NONE);
                } else {
                    setMode(EditMode.DELETE_MULTI_ITC);
                }
            });
        }

        // Regenerate Connections button
        const regenerateConnectionsBtn = document.getElementById('regenerateConnectionsBtn');
        if (regenerateConnectionsBtn) {
            regenerateConnectionsBtn.addEventListener('click', regenerateConnections);
        }

        // Sync Edit tab graph type with Configure tab on load
        const editGraphType = document.getElementById('editGraphType');
        if (editGraphType) {
            // Initialize from Configure tab's value
            const configGraphType = document.getElementById('neighbor_graph');
            if (configGraphType) {
                editGraphType.value = configGraphType.value;
            }

            // Listen for Configure tab changes
            document.addEventListener('paramsChanged', () => {
                const configVal = document.getElementById('neighbor_graph')?.value;
                if (configVal && editGraphType.value !== configVal) {
                    editGraphType.value = configVal;
                }
            });
        }

        // Area selection button
        const areaSelectBtn = document.getElementById('areaSelectBtn');
        if (areaSelectBtn) {
            areaSelectBtn.addEventListener('click', () => {
                if (currentMode === EditMode.AREA_SELECT) {
                    exitAreaSelectMode();
                } else {
                    enterAreaSelectMode();
                }
            });
        }

        // Delete selected (multi) button
        const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
        if (deleteSelectedBtn) {
            deleteSelectedBtn.addEventListener('click', deleteMultiSelected);
        }

        // Clear All button
        const clearAllBtn = document.getElementById('clearAllBtn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', clearAll);
        }

        // Listen for multi-selection changes to update button state
        document.addEventListener('multiSelectionChanged', (e) => {
            const { tubercleCount, edgeCount } = e.detail;
            const total = tubercleCount + edgeCount;

            // Update delete selected button
            const btn = document.getElementById('deleteSelectedBtn');
            if (btn) {
                btn.disabled = total === 0;
                btn.textContent = `Delete Selected (${total})`;
            }

            // Update multi-select status
            const status = document.getElementById('multiSelectStatus');
            if (status) {
                if (total === 0) {
                    status.textContent = 'No items selected';
                } else {
                    status.textContent = `${tubercleCount} tubercle(s), ${edgeCount} connection(s) selected`;
                }
            }
        });

        const undoBtn = document.getElementById('undoBtn');
        if (undoBtn) {
            undoBtn.addEventListener('click', () => window.undoManager?.undo());
        }

        const redoBtn = document.getElementById('redoBtn');
        if (redoBtn) {
            redoBtn.addEventListener('click', () => window.undoManager?.redo());
        }

        // Radius slider
        const radiusSlider = document.getElementById('radiusSlider');
        if (radiusSlider) {
            radiusSlider.addEventListener('input', (e) => {
                const val = parseFloat(e.target.value);
                setSelectedRadius(val);
                document.getElementById('radiusValue').textContent = val.toFixed(1) + 'px';
            });
        }

        // Radius +/- buttons
        const radiusIncBtn = document.getElementById('radiusIncBtn');
        if (radiusIncBtn) {
            radiusIncBtn.addEventListener('click', () => resizeSelected(1));
        }

        const radiusDecBtn = document.getElementById('radiusDecBtn');
        if (radiusDecBtn) {
            radiusDecBtn.addEventListener('click', () => resizeSelected(-1));
        }

        // Allow delete without confirm checkbox
        const allowDeleteCheck = document.getElementById('allowDeleteWithoutConfirm');
        if (allowDeleteCheck) {
            allowDeleteCheck.addEventListener('change', (e) => {
                setAllowDeleteWithoutConfirm(e.target.checked);
                updateDeleteMultipleButtons(e.target.checked);
            });
        }

        // Initialize delete multiple buttons state
        updateDeleteMultipleButtons(false);

        // Help icons for Edit tab
        const editHelpIcons = document.querySelectorAll('.help-icon[data-edit]');
        editHelpIcons.forEach(icon => {
            icon.addEventListener('click', (e) => {
                e.preventDefault();
                const topic = icon.dataset.edit;
                window.open(`/static/help/editing.html#${topic}`, 'help', 'width=800,height=600');
            });
        });

        // Update radius slider when selection changes
        document.addEventListener('tubercleSelected', (e) => {
            const tub = tubercles.find(t => t.id === e.detail.id);
            if (tub && radiusSlider) {
                radiusSlider.value = tub.radius_px;
                document.getElementById('radiusValue').textContent = tub.radius_px.toFixed(1) + 'px';
            }
            updateSelectionUI();
        });

        document.addEventListener('edgeSelected', () => {
            updateSelectionUI();
        });

        document.addEventListener('overlayDeselected', () => {
            updateSelectionUI();
        });
    }

    /**
     * Update UI based on selection state
     */
    function updateSelectionUI() {
        const selectedTub = window.overlay?.getSelectedTubercle();
        const selectedEdge = window.overlay?.getSelectedEdge();

        // Enable/disable buttons based on selection
        const moveBtn = document.getElementById('moveBtn');
        const deleteTubBtn = document.getElementById('deleteTubBtn');
        const deleteItcBtn = document.getElementById('deleteItcBtn');

        if (moveBtn) moveBtn.disabled = !selectedTub;
        if (deleteTubBtn) deleteTubBtn.disabled = !selectedTub;
        if (deleteItcBtn) deleteItcBtn.disabled = !selectedEdge;

        // Enable/disable radius controls (always visible, but disabled when no tubercle selected)
        const radiusSlider = document.getElementById('radiusSlider');
        const radiusIncBtn = document.getElementById('radiusIncBtn');
        const radiusDecBtn = document.getElementById('radiusDecBtn');
        const radiusHintSelect = document.getElementById('radiusHintSelect');
        const radiusHintUsage = document.getElementById('radiusHintUsage');

        if (radiusSlider) radiusSlider.disabled = !selectedTub;
        if (radiusIncBtn) radiusIncBtn.disabled = !selectedTub;
        if (radiusDecBtn) radiusDecBtn.disabled = !selectedTub;

        // Toggle hint messages
        if (radiusHintSelect) radiusHintSelect.style.display = selectedTub ? 'none' : 'block';
        if (radiusHintUsage) radiusHintUsage.style.display = selectedTub ? 'block' : 'none';
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        EditMode,
        setData,
        getData,
        setMode,
        getMode,
        cancelMode,
        handleCanvasClick,
        deleteSelected,
        deleteMultiSelected,
        clearAll,
        nudgeSelected,
        cycleSelection,
        areTubesVisible,
        areLinksVisible,
        enterAreaSelectMode,
        exitAreaSelectMode,
        chainGoBack,
        chainGoForward,
        chainCycleNext,
        chainCyclePrev,
        regenerateConnections,
        hasMultiSelection: () => window.overlay?.hasMultiSelection() || false,
        getDefaultDiameterUm,
        setDefaultDiameterUm,
        updateDefaultDiameterHint,
        isAutoSizeEnabled,
        setAutoSizeEnabled,
        updateAutoSizeHint,
    };
})();
