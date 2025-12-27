/**
 * Fish Scale Measurement UI - Undo/Redo System
 * Phase 3: Manual Editing Support
 * Updated: Now uses per-set undo/redo stacks via sets module
 */

window.undoManager = (function() {
    // Operation types
    const OperationType = {
        ADD_TUB: 'add_tub',
        DELETE_TUB: 'delete_tub',
        MOVE_TUB: 'move_tub',
        RESIZE_TUB: 'resize_tub',
        ADD_ITC: 'add_itc',
        DELETE_ITC: 'delete_itc',
        DELETE_MULTI: 'delete_multi',  // Batch delete tubercles and edges
    };

    /**
     * Push an operation onto the current set's undo stack
     * @param {Object} operation - The operation to push
     * @param {string} operation.type - Operation type from OperationType
     * @param {Object} operation.data - Operation-specific data for undo
     * @param {Object} operation.redoData - Operation-specific data for redo
     */
    function push(operation) {
        // Use the sets module's undo stack
        window.sets?.pushUndo(operation);
        updateUI();

        // Log the operation
        console.log('Undo stack push:', operation.type);
    }

    /**
     * Undo the last operation
     * @returns {Object|null} The undone operation or null if stack is empty
     */
    function undo() {
        const operation = window.sets?.popUndo();
        if (!operation) {
            return null;
        }

        updateUI();

        // Dispatch event for editor to handle
        document.dispatchEvent(new CustomEvent('undoOperation', {
            detail: { operation }
        }));

        return operation;
    }

    /**
     * Redo the last undone operation
     * @returns {Object|null} The redone operation or null if stack is empty
     */
    function redo() {
        const operation = window.sets?.popRedo();
        if (!operation) {
            return null;
        }

        updateUI();

        // Dispatch event for editor to handle
        document.dispatchEvent(new CustomEvent('redoOperation', {
            detail: { operation }
        }));

        return operation;
    }

    /**
     * Check if undo is available
     */
    function canUndo() {
        return window.sets?.canUndo() || false;
    }

    /**
     * Check if redo is available
     */
    function canRedo() {
        return window.sets?.canRedo() || false;
    }

    /**
     * Clear undo/redo history for current set
     */
    function clear() {
        window.sets?.clearUndoRedo();
        updateUI();
    }

    /**
     * Get the current stack sizes (for debugging)
     */
    function getStackSizes() {
        const undoStack = window.sets?.getUndoStack() || [];
        const redoStack = window.sets?.getRedoStack() || [];
        return {
            undo: undoStack.length,
            redo: redoStack.length,
        };
    }

    /**
     * Update UI elements (buttons, etc.)
     */
    function updateUI() {
        const undoBtn = document.getElementById('undoBtn');
        const redoBtn = document.getElementById('redoBtn');

        if (undoBtn) {
            undoBtn.disabled = !canUndo();
        }
        if (redoBtn) {
            redoBtn.disabled = !canRedo();
        }
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        updateUI();

        // Update UI when set changes
        document.addEventListener('setChanged', updateUI);
    });

    return {
        OperationType,
        push,
        undo,
        redo,
        canUndo,
        canRedo,
        clear,
        getStackSizes,
    };
})();
