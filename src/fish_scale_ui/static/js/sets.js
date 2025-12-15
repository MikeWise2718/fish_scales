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
     * Create a new set
     * @param {string} name - Set name
     * @param {Object} options - Options for initial content
     * @param {Array} options.tubercles - Initial tubercles
     * @param {Array} options.edges - Initial edges
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

        const newSet = {
            id: id,
            name: uniqueName,
            tubercles: options.tubercles ? JSON.parse(JSON.stringify(options.tubercles)) : [],
            edges: options.edges ? JSON.parse(JSON.stringify(options.edges)) : [],
            isDirty: false,
            undoStack: [],
            redoStack: [],
            createdAt: now,
            modifiedAt: now,
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
        return createSet(name, {
            tubercles: source.tubercles,
            edges: source.edges,
        });
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

    /**
     * Export all sets data for saving to SLO
     * @returns {Object} Data structure for v2 SLO format
     */
    function exportForSave() {
        return {
            activeSetId: currentSetId,
            sets: setOrder.map(id => ({
                id: sets[id].id,
                name: sets[id].name,
                createdAt: sets[id].createdAt,
                modifiedAt: sets[id].modifiedAt,
                tubercles: sets[id].tubercles,
                edges: sets[id].edges,
            })),
        };
    }

    /**
     * Import sets data from loaded SLO (v2 format)
     * @param {Object} data - Data from SLO file
     */
    function importFromLoad(data) {
        clear();

        if (!data.sets || data.sets.length === 0) {
            // Fallback to default set
            init();
            return;
        }

        data.sets.forEach(setData => {
            const id = setData.id || generateId();
            const now = new Date().toISOString();

            sets[id] = {
                id: id,
                name: setData.name || 'Unnamed',
                tubercles: setData.tubercles || [],
                edges: setData.edges || [],
                isDirty: false,
                undoStack: [],
                redoStack: [],
                createdAt: setData.createdAt || now,
                modifiedAt: setData.modifiedAt || now,
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
     * Import from v1 SLO format (single set)
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

        // Dirty state
        markDirty,
        markClean,
        markAllClean,
        hasUnsavedChanges,
        anyUnsavedChanges,

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

        // Utility
        getSetCount,
        canCreateMore,
        sanitizeName,
        makeNameUnique,
    };
})();
