/**
 * Fish Scale Measurement UI - Sets Module
 * Manages multiple tubercle/link annotation sets per image
 */

window.sets = (function() {
    const MAX_SETS = 10;
    const MAX_NAME_LENGTH = 20;
    const FORBIDDEN_CHARS = /[\/\\:*?"<>|]/g;

    // State
    let currentSetId = null;
    let sets = {};
    let setOrder = [];

    /**
     * Generate a unique set ID
     */
    function generateId() {
        return 'set_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Validate and sanitize a set name
     */
    function sanitizeName(name) {
        let sanitized = (name || '').trim().replace(FORBIDDEN_CHARS, '');
        if (sanitized.length > MAX_NAME_LENGTH) {
            sanitized = sanitized.substring(0, MAX_NAME_LENGTH);
        }
        return sanitized || 'Unnamed';
    }

    /**
     * Check if a name is unique among existing sets
     */
    function isNameUnique(name, excludeId = null) {
        return !Object.values(sets).some(s =>
            s.id !== excludeId && s.name.toLowerCase() === name.toLowerCase()
        );
    }

    /**
     * Make a name unique by appending a number if needed
     */
    function makeNameUnique(baseName, excludeId = null) {
        let name = sanitizeName(baseName);
        if (isNameUnique(name, excludeId)) {
            return name;
        }

        let counter = 2;
        let newName = name;
        while (!isNameUnique(newName, excludeId)) {
            const suffix = ` (${counter})`;
            const maxBase = MAX_NAME_LENGTH - suffix.length;
            newName = name.substring(0, maxBase) + suffix;
            counter++;
        }
        return newName;
    }

    /**
     * Initialize with a default "Base" set
     */
    function init() {
        clear();
        createSet('Base');
    }

    /**
     * Clear all sets and reset state
     */
    function clear() {
        sets = {};
        setOrder = [];
        currentSetId = null;
    }

    /**
     * Get current calibration um_per_pixel value
     * @returns {number|null} Calibration value or null if not set
     */
    function getCurrentCalibrationValue() {
        const calibration = window.calibration?.getCurrentCalibration();
        return calibration?.um_per_px || null;
    }

    /**
     * Create a new set
     * @param {string} name - Set name
     * @param {Object} options - Options for initial content
     * @param {Array} options.tubercles - Initial tubercles
     * @param {Array} options.edges - Initial edges
     * @param {Object} options.parameters - Extraction parameters used to create this set
     * @param {number} options.calibration_um_per_pixel - Calibration snapshot (auto-captured if not provided)
     * @returns {Object} The created set or null if max sets reached
     */
    function createSet(name, options = {}) {
        if (setOrder.length >= MAX_SETS) {
            console.warn('Maximum number of sets reached');
            return null;
        }

        const id = generateId();
        const uniqueName = makeNameUnique(name);
        const now = new Date().toISOString();

        // Mark as dirty if created with data (needs saving to disk)
        const hasData = (options.tubercles && options.tubercles.length > 0) ||
                        (options.edges && options.edges.length > 0);

        // Capture calibration snapshot - use provided value or current calibration
        const calibrationSnapshot = options.calibration_um_per_pixel !== undefined
            ? options.calibration_um_per_pixel
            : getCurrentCalibrationValue();

        const newSet = {
            id: id,
            name: uniqueName,
            tubercles: options.tubercles ? JSON.parse(JSON.stringify(options.tubercles)) : [],
            edges: options.edges ? JSON.parse(JSON.stringify(options.edges)) : [],
            parameters: options.parameters ? JSON.parse(JSON.stringify(options.parameters)) : null,
            calibration_um_per_pixel: calibrationSnapshot,  // v3.0: per-set calibration snapshot
            isDirty: hasData,
            undoStack: [],
            redoStack: [],
            createdAt: now,
            modifiedAt: now,
            history: options.history ? JSON.parse(JSON.stringify(options.history)) : [],
            pendingEdits: {
                added_tubercles: 0,
                deleted_tubercles: 0,
                moved_tubercles: 0,
                resized_tubercles: 0,
                added_connections: 0,
                deleted_connections: 0,
            },
        };

        sets[id] = newSet;
        setOrder.push(id);

        // If this is the first set, make it active
        if (setOrder.length === 1) {
            currentSetId = id;
        }

        // Dispatch event
        document.dispatchEvent(new CustomEvent('setCreated', {
            detail: { set: newSet }
        }));

        return newSet;
    }

    /**
     * Get a set by ID
     */
    function getSet(setId) {
        return sets[setId] || null;
    }

    /**
     * Get the currently active set
     */
    function getCurrentSet() {
        return sets[currentSetId] || null;
    }

    /**
     * Get the current set ID
     */
    function getCurrentSetId() {
        return currentSetId;
    }

    /**
     * Get list of all sets (for UI)
     */
    function getSetList() {
        return setOrder.map(id => ({
            id: sets[id].id,
            name: sets[id].name,
            isDirty: sets[id].isDirty,
            tubercleCount: sets[id].tubercles.length,
            edgeCount: sets[id].edges.length,
        }));
    }

    /**
     * Switch to a different set
     * @param {string} setId - ID of set to switch to
     * @returns {boolean} True if switch was successful
     */
    function switchSet(setId) {
        if (!sets[setId]) {
            console.warn('Set not found:', setId);
            return false;
        }

        if (setId === currentSetId) {
            return true; // Already active
        }

        const previousSetId = currentSetId;
        currentSetId = setId;

        // Dispatch event
        document.dispatchEvent(new CustomEvent('setChanged', {
            detail: {
                previousSetId,
                currentSetId: setId,
                set: sets[setId],
            }
        }));

        return true;
    }

    /**
     * Delete a set
     * @param {string} setId - ID of set to delete
     * @returns {boolean} True if deletion was successful
     */
    function deleteSet(setId) {
        if (!sets[setId]) {
            console.warn('Set not found:', setId);
            return false;
        }

        // Cannot delete the last set
        if (setOrder.length <= 1) {
            console.warn('Cannot delete the last set');
            return false;
        }

        const deletedSet = sets[setId];
        const wasActive = (setId === currentSetId);

        // Remove from order
        const idx = setOrder.indexOf(setId);
        if (idx !== -1) {
            setOrder.splice(idx, 1);
        }

        // Remove from sets
        delete sets[setId];

        // If we deleted the active set, switch to another
        if (wasActive && setOrder.length > 0) {
            // Switch to the set at the same position, or the last one
            const newIdx = Math.min(idx, setOrder.length - 1);
            switchSet(setOrder[newIdx]);
        }

        // Dispatch event
        document.dispatchEvent(new CustomEvent('setDeleted', {
            detail: { setId, deletedSet }
        }));

        return true;
    }

    /**
     * Rename a set
     * @param {string} setId - ID of set to rename
     * @param {string} newName - New name
     * @returns {boolean} True if rename was successful
     */
    function renameSet(setId, newName) {
        if (!sets[setId]) {
            console.warn('Set not found:', setId);
            return false;
        }

        const sanitized = sanitizeName(newName);
        if (!isNameUnique(sanitized, setId)) {
            console.warn('Name already exists:', sanitized);
            return false;
        }

        const oldName = sets[setId].name;
        sets[setId].name = sanitized;

        // Dispatch event
        document.dispatchEvent(new CustomEvent('setRenamed', {
            detail: { setId, oldName, newName: sanitized }
        }));

        return true;
    }

    /**
     * Duplicate a set
     * @param {string} setId - ID of set to duplicate
     * @param {string} newName - Name for the duplicate
     * @returns {Object} The duplicated set or null
     */
    function duplicateSet(setId, newName = null) {
        const source = sets[setId];
        if (!source) {
            console.warn('Set not found:', setId);
            return null;
        }

        const name = newName || (source.name + ' Copy');
        const newSet = createSet(name, {
            tubercles: source.tubercles,
            edges: source.edges,
            parameters: source.parameters,  // Copy extraction parameters
            // Start with empty history for the clone
            history: [],
        });

        if (newSet) {
            // Add clone event to the new set's history
            addHistoryEvent('clone', {
                source_set_id: source.id,
                source_set_name: source.name,
                n_tubercles: source.tubercles.length,
                n_edges: source.edges.length,
            }, newSet.id);
        }

        return newSet;
    }

    /**
     * Set data for the current set
     * @param {Array} tubercles - Tubercle data
     * @param {Array} edges - Edge data
     */
    function setCurrentData(tubercles, edges) {
        const set = getCurrentSet();
        if (!set) return;

        set.tubercles = tubercles || [];
        set.edges = edges || [];
        set.modifiedAt = new Date().toISOString();

        // Dispatch event
        document.dispatchEvent(new CustomEvent('setDataChanged', {
            detail: { setId: set.id }
        }));
    }

    /**
     * Get data from the current set
     * @returns {Object} Object with tubercles and edges arrays
     */
    function getCurrentData() {
        const set = getCurrentSet();
        if (!set) {
            return { tubercles: [], edges: [] };
        }
        return {
            tubercles: set.tubercles,
            edges: set.edges,
        };
    }

    /**
     * Get parameters for the current set
     * @returns {Object|null} Parameters object or null if not set
     */
    function getCurrentParameters() {
        const set = getCurrentSet();
        return set ? set.parameters : null;
    }

    /**
     * Set parameters for the current set
     * @param {Object} params - Extraction parameters
     */
    function setCurrentParameters(params) {
        const set = getCurrentSet();
        if (!set) return;

        set.parameters = params ? JSON.parse(JSON.stringify(params)) : null;
        set.modifiedAt = new Date().toISOString();

        // Dispatch event
        document.dispatchEvent(new CustomEvent('setParametersChanged', {
            detail: { setId: set.id, parameters: set.parameters }
        }));
    }

    /**
     * Get calibration for a set
     * @param {string} setId - Set ID (defaults to current)
     * @returns {number|null} Calibration um_per_pixel value or null
     */
    function getSetCalibration(setId = null) {
        const id = setId || currentSetId;
        const set = sets[id];
        return set ? set.calibration_um_per_pixel : null;
    }

    /**
     * Update calibration for a set (used when recalculating)
     * @param {number} calibration - New calibration value
     * @param {string} setId - Set ID (defaults to current)
     */
    function setSetCalibration(calibration, setId = null) {
        const id = setId || currentSetId;
        const set = sets[id];
        if (!set) return;

        set.calibration_um_per_pixel = calibration;
        set.modifiedAt = new Date().toISOString();

        // Dispatch event
        document.dispatchEvent(new CustomEvent('setCalibrationChanged', {
            detail: { setId: id, calibration: calibration }
        }));
    }

    /**
     * Check if set calibration matches current calibration
     * @param {string} setId - Set ID (defaults to current)
     * @returns {Object} { matches: boolean, setCal: number, currentCal: number }
     */
    function checkCalibrationMatch(setId = null) {
        const id = setId || currentSetId;
        const set = sets[id];
        const currentCal = getCurrentCalibrationValue();
        const setCal = set?.calibration_um_per_pixel;

        // Handle cases where calibration isn't set
        if (setCal === null || setCal === undefined || currentCal === null) {
            return { matches: true, setCal, currentCal, legacy: setCal === null || setCal === undefined };
        }

        // Compare with small tolerance for floating point
        const tolerance = 0.0001;
        const matches = Math.abs(setCal - currentCal) < tolerance;

        return { matches, setCal, currentCal, legacy: false };
    }

    /**
     * Mark a set as dirty (has unsaved changes)
     * @param {string} setId - Set ID (defaults to current)
     */
    function markDirty(setId = null) {
        const id = setId || currentSetId;
        if (!sets[id]) return;

        const wasDirty = sets[id].isDirty;
        sets[id].isDirty = true;
        sets[id].modifiedAt = new Date().toISOString();

        if (!wasDirty) {
            document.dispatchEvent(new CustomEvent('setDirtyStateChanged', {
                detail: { setId: id, isDirty: true }
            }));
        }
    }

    /**
     * Mark a set as clean (saved)
     * @param {string} setId - Set ID (defaults to current)
     */
    function markClean(setId = null) {
        const id = setId || currentSetId;
        if (!sets[id]) return;

        const wasDirty = sets[id].isDirty;
        sets[id].isDirty = false;

        if (wasDirty) {
            document.dispatchEvent(new CustomEvent('setDirtyStateChanged', {
                detail: { setId: id, isDirty: false }
            }));
        }
    }

    /**
     * Mark all sets as clean
     */
    function markAllClean() {
        setOrder.forEach(id => markClean(id));
    }

    /**
     * Check if a set has unsaved changes
     * @param {string} setId - Set ID (defaults to current)
     */
    function hasUnsavedChanges(setId = null) {
        const id = setId || currentSetId;
        return sets[id] ? sets[id].isDirty : false;
    }

    /**
     * Check if ANY set has unsaved changes
     */
    function anyUnsavedChanges() {
        return setOrder.some(id => sets[id].isDirty);
    }

    /**
     * Check if ANY set has data (tubercles or edges)
     */
    function hasAnyData() {
        return setOrder.some(id => {
            const set = sets[id];
            return set && (set.tubercles.length > 0 || set.edges.length > 0);
        });
    }

    /**
     * Get the undo stack for the current set
     */
    function getUndoStack() {
        const set = getCurrentSet();
        return set ? set.undoStack : [];
    }

    /**
     * Get the redo stack for the current set
     */
    function getRedoStack() {
        const set = getCurrentSet();
        return set ? set.redoStack : [];
    }

    /**
     * Push an operation to the current set's undo stack
     */
    function pushUndo(operation) {
        const set = getCurrentSet();
        if (!set) return;

        set.undoStack.push(operation);
        set.redoStack = []; // Clear redo on new action

        // Enforce max stack size
        const MAX_STACK_SIZE = 100;
        if (set.undoStack.length > MAX_STACK_SIZE) {
            set.undoStack.shift();
        }
    }

    /**
     * Pop from the current set's undo stack
     */
    function popUndo() {
        const set = getCurrentSet();
        if (!set || set.undoStack.length === 0) return null;

        const operation = set.undoStack.pop();
        set.redoStack.push(operation);
        return operation;
    }

    /**
     * Pop from the current set's redo stack
     */
    function popRedo() {
        const set = getCurrentSet();
        if (!set || set.redoStack.length === 0) return null;

        const operation = set.redoStack.pop();
        set.undoStack.push(operation);
        return operation;
    }

    /**
     * Clear undo/redo stacks for the current set
     */
    function clearUndoRedo() {
        const set = getCurrentSet();
        if (!set) return;

        set.undoStack = [];
        set.redoStack = [];
    }

    /**
     * Check if undo is available for current set
     */
    function canUndo() {
        const set = getCurrentSet();
        return set ? set.undoStack.length > 0 : false;
    }

    /**
     * Check if redo is available for current set
     */
    function canRedo() {
        const set = getCurrentSet();
        return set ? set.redoStack.length > 0 : false;
    }

    // ===== History Management =====

    /**
     * Add a history event to a set
     * @param {string} eventType - Event type (extraction, auto_connect, manual_edit, agent_phase, clone, import)
     * @param {Object} data - Event-specific data
     * @param {string} setId - Set ID (defaults to current)
     */
    function addHistoryEvent(eventType, data = {}, setId = null) {
        const id = setId || currentSetId;
        const set = sets[id];
        if (!set) return;

        // Get current user
        const user = window.user?.getCurrentUser() || 'Unknown';

        const event = {
            timestamp: new Date().toISOString(),
            type: eventType,
            user: user,
            ...data,
        };

        set.history.push(event);

        // Dispatch event so UI can update
        document.dispatchEvent(new CustomEvent('historyChanged', {
            detail: { setId: id, event }
        }));
    }

    /**
     * Get history for a set
     * @param {string} setId - Set ID (defaults to current)
     * @returns {Array} History events
     */
    function getHistory(setId = null) {
        const id = setId || currentSetId;
        const set = sets[id];
        return set ? set.history : [];
    }

    /**
     * Track a pending edit (for consolidation on save)
     * @param {string} editType - Edit type (added_tubercles, deleted_tubercles, etc.)
     * @param {number} count - Number to add (default 1)
     * @param {string} setId - Set ID (defaults to current)
     */
    function trackEdit(editType, count = 1, setId = null) {
        const id = setId || currentSetId;
        const set = sets[id];
        if (!set || !set.pendingEdits.hasOwnProperty(editType)) return;

        set.pendingEdits[editType] += count;
    }

    /**
     * Consolidate pending edits into a history event
     * Called before save to record all edits since last save
     * @param {string} setId - Set ID (defaults to current)
     */
    async function consolidateEdits(setId = null) {
        const id = setId || currentSetId;
        const set = sets[id];
        if (!set) return;

        const edits = set.pendingEdits;

        // Check if any edits were made
        const hasEdits = Object.values(edits).some(v => v > 0);
        if (!hasEdits) return;

        // Create summary
        const summary = [];
        if (edits.added_tubercles > 0) summary.push(`+${edits.added_tubercles} tubercles`);
        if (edits.deleted_tubercles > 0) summary.push(`-${edits.deleted_tubercles} tubercles`);
        if (edits.moved_tubercles > 0) summary.push(`${edits.moved_tubercles} moved`);
        if (edits.resized_tubercles > 0) summary.push(`${edits.resized_tubercles} resized`);
        if (edits.added_connections > 0) summary.push(`+${edits.added_connections} connections`);
        if (edits.deleted_connections > 0) summary.push(`-${edits.deleted_connections} connections`);

        // Calculate hexagonalness for result (uses current server state)
        const tubercles = set.tubercles;
        const edges = set.edges;
        const hexStats = await window.extraction?.calculateHexagonalness?.();

        // Add history event
        addHistoryEvent('manual_edit', {
            summary: summary.join(', '),
            details: { ...edits },
            result: {
                n_tubercles: tubercles.length,
                n_edges: edges.length,
                hexagonalness: hexStats?.hexagonalness_score || 0,
            },
        }, id);

        // Reset pending edits
        resetPendingEdits(id);
    }

    /**
     * Reset pending edits for a set
     * @param {string} setId - Set ID (defaults to current)
     */
    function resetPendingEdits(setId = null) {
        const id = setId || currentSetId;
        const set = sets[id];
        if (!set) return;

        set.pendingEdits = {
            added_tubercles: 0,
            deleted_tubercles: 0,
            moved_tubercles: 0,
            resized_tubercles: 0,
            added_connections: 0,
            deleted_connections: 0,
        };
    }

    /**
     * Get pending edits for a set
     * @param {string} setId - Set ID (defaults to current)
     * @returns {Object} Pending edits counts
     */
    function getPendingEdits(setId = null) {
        const id = setId || currentSetId;
        const set = sets[id];
        return set ? { ...set.pendingEdits } : {};
    }

    /**
     * Export all sets data for saving to annotations
     * @returns {Promise<Object>} Data structure for v3 annotations format
     */
    async function exportForSave() {
        // Consolidate pending edits for all sets before exporting
        for (const id of setOrder) {
            await consolidateEdits(id);
        }

        return {
            activeSetId: currentSetId,
            sets: setOrder.map(id => ({
                id: sets[id].id,
                name: sets[id].name,
                createdAt: sets[id].createdAt,
                modifiedAt: sets[id].modifiedAt,
                calibration_um_per_pixel: sets[id].calibration_um_per_pixel,  // v3.0: per-set calibration
                tubercles: sets[id].tubercles,
                edges: sets[id].edges,
                parameters: sets[id].parameters,  // Include extraction parameters
                history: sets[id].history,
            })),
        };
    }

    /**
     * Import sets data from loaded annotations (v2/v3 format)
     * @param {Object} data - Data from annotations file
     */
    function importFromLoad(data) {
        clear();

        if (!data.sets || data.sets.length === 0) {
            // Fallback to default set
            init();
            return;
        }

        // Get current calibration for fallback (legacy sets without calibration snapshot)
        const currentCalibration = getCurrentCalibrationValue();

        data.sets.forEach(setData => {
            const id = setData.id || generateId();
            const now = new Date().toISOString();

            sets[id] = {
                id: id,
                name: setData.name || 'Unnamed',
                tubercles: setData.tubercles || [],
                edges: setData.edges || [],
                parameters: setData.parameters || null,  // Load extraction parameters
                // v3.0: per-set calibration snapshot (fallback to current for legacy)
                calibration_um_per_pixel: setData.calibration_um_per_pixel ?? currentCalibration,
                isDirty: false,
                undoStack: [],
                redoStack: [],
                createdAt: setData.createdAt || now,
                modifiedAt: setData.modifiedAt || now,
                history: setData.history || [],
                pendingEdits: {
                    added_tubercles: 0,
                    deleted_tubercles: 0,
                    moved_tubercles: 0,
                    resized_tubercles: 0,
                    added_connections: 0,
                    deleted_connections: 0,
                },
            };
            setOrder.push(id);
        });

        // Set active set
        if (data.activeSetId && sets[data.activeSetId]) {
            currentSetId = data.activeSetId;
        } else {
            currentSetId = setOrder[0];
        }

        // Dispatch event
        document.dispatchEvent(new CustomEvent('setsLoaded', {
            detail: { setCount: setOrder.length }
        }));
    }

    /**
     * Import from v1 annotations format (single set)
     * @param {Array} tubercles - Tubercle data
     * @param {Array} edges - Edge data
     */
    function importFromV1(tubercles, edges) {
        clear();
        const set = createSet('Base', { tubercles, edges });
        currentSetId = set.id;

        // Dispatch event
        document.dispatchEvent(new CustomEvent('setsLoaded', {
            detail: { setCount: 1, fromV1: true }
        }));
    }

    /**
     * Get set count
     */
    function getSetCount() {
        return setOrder.length;
    }

    /**
     * Check if we can create more sets
     */
    function canCreateMore() {
        return setOrder.length < MAX_SETS;
    }

    // Initialize on DOM ready with a default set
    document.addEventListener('DOMContentLoaded', init);

    return {
        // Core operations
        init,
        clear,
        createSet,
        getSet,
        getCurrentSet,
        getCurrentSetId,
        getSetList,
        switchSet,
        deleteSet,
        renameSet,
        duplicateSet,

        // Data operations
        setCurrentData,
        getCurrentData,
        getCurrentParameters,
        setCurrentParameters,

        // Calibration operations (v3.0)
        getSetCalibration,
        setSetCalibration,
        checkCalibrationMatch,

        // Dirty state
        markDirty,
        markClean,
        markAllClean,
        hasUnsavedChanges,
        anyUnsavedChanges,
        hasAnyData,

        // Undo/redo
        getUndoStack,
        getRedoStack,
        pushUndo,
        popUndo,
        popRedo,
        clearUndoRedo,
        canUndo,
        canRedo,

        // Import/Export
        exportForSave,
        importFromLoad,
        importFromV1,

        // History
        addHistoryEvent,
        getHistory,
        trackEdit,
        consolidateEdits,
        resetPendingEdits,
        getPendingEdits,

        // Utility
        getSetCount,
        canCreateMore,
        sanitizeName,
        makeNameUnique,
    };
})();
