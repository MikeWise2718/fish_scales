/**
 * Fish Scale Measurement UI - Undo/Redo System
 * Phase 3: Manual Editing Support
 */

window.undoManager = (function() {
    const MAX_STACK_SIZE = 100;

    // Undo and redo stacks
    let undoStack = [];
    let redoStack = [];

    // Operation types
    const OperationType = {
        ADD_TUB: 'add_tub',
        DELETE_TUB: 'delete_tub',
        MOVE_TUB: 'move_tub',
        RESIZE_TUB: 'resize_tub',
        ADD_ITC: 'add_itc',
        DELETE_ITC: 'delete_itc',
    };

    /**
     * Push an operation onto the undo stack
     * @param {Object} operation - The operation to push
     * @param {string} operation.type - Operation type from OperationType
     * @param {Object} operation.data - Operation-specific data for undo
     * @param {Object} operation.redoData - Operation-specific data for redo
     */
    function push(operation) {
        undoStack.push(operation);

        // Clear redo stack when new action is performed
        redoStack = [];

        // Enforce max stack size
        if (undoStack.length > MAX_STACK_SIZE) {
            undoStack.shift();
        }

        updateUI();

        // Log the operation
        console.log('Undo stack push:', operation.type);
    }

    /**
     * Undo the last operation
     * @returns {Object|null} The undone operation or null if stack is empty
     */
    function undo() {
        if (undoStack.length === 0) {
            return null;
        }

        const operation = undoStack.pop();
        redoStack.push(operation);

        // Enforce max redo stack size
        if (redoStack.length > MAX_STACK_SIZE) {
            redoStack.shift();
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
        if (redoStack.length === 0) {
            return null;
        }

        const operation = redoStack.pop();
        undoStack.push(operation);

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
        return undoStack.length > 0;
    }

    /**
     * Check if redo is available
     */
    function canRedo() {
        return redoStack.length > 0;
    }

    /**
     * Clear all undo/redo history
     */
    function clear() {
        undoStack = [];
        redoStack = [];
        updateUI();
    }

    /**
     * Get the current stack sizes (for debugging)
     */
    function getStackSizes() {
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
