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
        MOVE: 'move',
        DELETE_MULTI_TUB: 'delete_multi_tub',
        DELETE_MULTI_ITC: 'delete_multi_itc',
    };

    // Current state
    let currentMode = EditMode.NONE;
    let pendingFirstTub = null; // For ITC creation - first selected tubercle
    let allowDeleteWithoutConfirm = false;
    let defaultRadius = null; // Will be set from mean diameter

    // Data references (synced with overlay and data modules)
    let tubercles = [];
    let edges = [];
    let nextTubId = 1;

    // Get current calibration for conversions
    function getCalibration() {
        return window.calibration?.getCurrentCalibration();
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
     * Update UI to reflect current mode
     */
    function updateModeUI() {
        // Update buttons
        const addTubBtn = document.getElementById('addTubBtn');
        const addItcBtn = document.getElementById('addItcBtn');
        const moveBtn = document.getElementById('moveBtn');
        const deleteMultipleTubBtn = document.getElementById('deleteMultipleTubBtn');
        const deleteMultipleItcBtn = document.getElementById('deleteMultipleItcBtn');

        if (addTubBtn) {
            addTubBtn.classList.toggle('active', currentMode === EditMode.ADD_TUB);
        }
        if (addItcBtn) {
            addItcBtn.classList.toggle('active', currentMode === EditMode.ADD_ITC);
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
                case EditMode.MOVE:
                    statusEl.textContent = 'Click destination to move selected tubercle';
                    break;
                case EditMode.DELETE_MULTI_TUB:
                    statusEl.textContent = 'Click tubercles to delete them';
                    break;
                case EditMode.DELETE_MULTI_ITC:
                    statusEl.textContent = 'Click connections to delete them';
                    break;
                default:
                    statusEl.textContent = '';
            }
        }
    }

    /**
     * Update cursor based on mode
     */
    function updateCursor() {
        const container = document.getElementById('imageContainer');
        if (!container) return;

        switch (currentMode) {
            case EditMode.ADD_TUB:
                container.style.cursor = 'crosshair';
                break;
            case EditMode.ADD_ITC:
                container.style.cursor = 'pointer';
                break;
            case EditMode.MOVE:
                container.style.cursor = 'move';
                break;
            case EditMode.DELETE_MULTI_TUB:
            case EditMode.DELETE_MULTI_ITC:
                container.style.cursor = 'crosshair';
                break;
            default:
                container.style.cursor = '';
        }
    }

    /**
     * Handle click on the overlay canvas
     */
    function handleCanvasClick(x, y) {
        switch (currentMode) {
            case EditMode.ADD_TUB:
                addTubercle(x, y);
                break;
            case EditMode.ADD_ITC:
                handleItcClick(x, y);
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
    function addTubercle(x, y) {
        const calibration = getCalibration();
        const umPerPx = calibration?.um_per_px || 0.14;

        const newTub = {
            id: nextTubId++,
            centroid_x: x,
            centroid_y: y,
            radius_px: defaultRadius,
            diameter_um: (defaultRadius * 2) * umPerPx,
            circularity: 1.0, // Perfect circle for manual addition
        };

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
        logEdit('add_tub', { id: newTub.id, x: x.toFixed(1), y: y.toFixed(1), radius: defaultRadius.toFixed(1) });

        // Stay in add mode for multiple additions
        window.app?.showToast(`Added tubercle #${newTub.id}`, 'success');
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
        logEdit('delete_tub', { id });

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
        logEdit('delete_itc', { id1: edge.id1, id2: edge.id2 });

        window.app?.showToast(`Deleted connection ${edge.id1}-${edge.id2}`, 'success');
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
    function refreshDisplays() {
        // Update overlay
        window.overlay?.setData(tubercles, edges);

        // Update data tables
        const stats = calculateStatistics();
        window.data?.setData(tubercles, edges, stats);
    }

    /**
     * Calculate statistics from current data
     */
    function calculateStatistics() {
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

        // Calculate hexagonalness metrics
        const hexMetrics = calculateHexagonalness(tubercles, edges);

        return {
            n_tubercles,
            n_edges,
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
     * Calculate hexagonalness metrics for the current data
     */
    function calculateHexagonalness(tubercles, edges) {
        const MIN_NODES_FOR_RELIABLE = 15;

        const result = {
            hexagonalness_score: 0.0,
            spacing_uniformity: 0.0,
            degree_score: 0.0,
            edge_ratio_score: 0.0,
            mean_degree: 0.0,
            degree_histogram: {},
            spacing_cv: 1.0,
            reliability: 'none',
            n_nodes: 0,
        };

        if (!tubercles || tubercles.length < 4) {
            return result;
        }

        const n_nodes = tubercles.length;
        result.n_nodes = n_nodes;
        result.reliability = n_nodes >= MIN_NODES_FOR_RELIABLE ? 'high' : 'low';

        // 1. Spacing uniformity (coefficient of variation)
        if (edges && edges.length > 0) {
            const spacings = edges
                .map(e => e.edge_distance_um)
                .filter(s => s > 0);

            if (spacings.length > 0) {
                const mean = spacings.reduce((a, b) => a + b, 0) / spacings.length;
                const variance = spacings.reduce((sum, s) => sum + Math.pow(s - mean, 2), 0) / spacings.length;
                const std = Math.sqrt(variance);
                const cv = mean > 0 ? std / mean : 1.0;
                result.spacing_cv = cv;
                result.spacing_uniformity = Math.max(0, 1 - 2 * cv);
            }
        }

        // 2. Degree distribution (neighbors per node)
        const degree = {};

        // Initialize all nodes with degree 0
        tubercles.forEach(t => { degree[t.id] = 0; });

        // Count connections (use object key lookup for type coercion)
        edges.forEach(e => {
            const aId = e.tubercle_a_id ?? e.id1;
            const bId = e.tubercle_b_id ?? e.id2;
            if (degree[aId] !== undefined) degree[aId]++;
            if (degree[bId] !== undefined) degree[bId]++;
        });

        const degrees = Object.values(degree);
        if (degrees.length > 0) {
            result.mean_degree = degrees.reduce((a, b) => a + b, 0) / degrees.length;

            // Build histogram
            const histogram = {};
            degrees.forEach(d => {
                histogram[d] = (histogram[d] || 0) + 1;
            });
            result.degree_histogram = histogram;

            // Weighted score for degree distribution
            let weightedScore = 0;
            degrees.forEach(d => {
                if (d >= 5 && d <= 7) weightedScore += 1.0;
                else if (d === 4 || d === 8) weightedScore += 0.7;
                else if (d === 3 || d === 9) weightedScore += 0.3;
            });
            result.degree_score = weightedScore / degrees.length;
        }

        // 3. Edge/node ratio
        if (n_nodes > 0) {
            const ratio = edges.length / n_nodes;
            const idealRatio = 2.5;
            const deviation = Math.abs(ratio - idealRatio);
            result.edge_ratio_score = Math.max(0, 1 - deviation / 2);
        }

        // 4. Composite score
        result.hexagonalness_score = (
            0.40 * result.spacing_uniformity +
            0.45 * result.degree_score +
            0.15 * result.edge_ratio_score
        );

        return result;
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
        }

        refreshDisplays();
        markDirty();
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
        }

        refreshDisplays();
        markDirty();
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
        nudgeSelected,
        cycleSelection,
        areTubesVisible,
        areLinksVisible,
    };
})();
