/**
 * Fish Scale Measurement UI - User Management
 *
 * Handles user identity for history tracking.
 */

window.user = (function() {
    let currentUser = null;
    let userSource = null;
    let isOverridable = true;

    /**
     * Initialize user module by fetching current user from server.
     */
    async function init() {
        try {
            const response = await fetch('/api/user');
            const data = await response.json();
            currentUser = data.user;
            userSource = data.source;
            isOverridable = data.overridable;
            updateUI();
        } catch (err) {
            console.error('Failed to load user:', err);
            currentUser = 'Unknown';
            userSource = 'error';
            isOverridable = false;
        }
    }

    /**
     * Get the current user name.
     * @returns {string} Current user name
     */
    function getCurrentUser() {
        return currentUser || 'Unknown';
    }

    /**
     * Get the source of the current user name.
     * @returns {string} One of: 'environment', 'config', 'default', 'error'
     */
    function getSource() {
        return userSource || 'unknown';
    }

    /**
     * Check if user can be changed via UI.
     * @returns {boolean} True if user is changeable
     */
    function canChange() {
        return isOverridable;
    }

    /**
     * Set the user name.
     * @param {string} userName - New user name
     * @returns {Promise<boolean>} True if successful
     */
    async function setUser(userName) {
        if (!isOverridable) {
            window.app?.showToast('User is set by environment variable', 'warning');
            return false;
        }

        try {
            const response = await fetch('/api/user', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user: userName }),
            });

            const data = await response.json();

            if (data.error) {
                window.app?.showToast(data.error, 'error');
                return false;
            }

            currentUser = data.user;
            userSource = data.source;
            updateUI();
            window.app?.showToast('User updated', 'success');
            return true;
        } catch (err) {
            console.error('Failed to set user:', err);
            window.app?.showToast('Failed to update user', 'error');
            return false;
        }
    }

    /**
     * Update UI elements to reflect current user state.
     */
    function updateUI() {
        // Update user input field
        const userInput = document.getElementById('userNameInput');
        if (userInput) {
            userInput.value = currentUser || '';
            userInput.disabled = !isOverridable;
        }

        // Update save button
        const saveBtn = document.getElementById('saveUserBtn');
        if (saveBtn) {
            saveBtn.disabled = !isOverridable;
        }

        // Update source indicator
        const sourceSpan = document.getElementById('userSourceIndicator');
        if (sourceSpan) {
            if (userSource === 'environment') {
                sourceSpan.textContent = '(set by environment variable)';
                sourceSpan.className = 'user-source-hint locked';
            } else if (userSource === 'config') {
                sourceSpan.textContent = '(saved in config)';
                sourceSpan.className = 'user-source-hint';
            } else if (userSource === 'default') {
                sourceSpan.textContent = '(default)';
                sourceSpan.className = 'user-source-hint default';
            } else {
                sourceSpan.textContent = '';
                sourceSpan.className = 'user-source-hint';
            }
        }
    }

    /**
     * Handle save button click.
     */
    function handleSave() {
        const userInput = document.getElementById('userNameInput');
        if (userInput && userInput.value.trim()) {
            setUser(userInput.value.trim());
        }
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', () => {
        init();

        // Bind save button
        const saveBtn = document.getElementById('saveUserBtn');
        if (saveBtn) {
            saveBtn.addEventListener('click', handleSave);
        }

        // Bind Enter key in input
        const userInput = document.getElementById('userNameInput');
        if (userInput) {
            userInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    handleSave();
                }
            });
        }
    });

    return {
        init,
        getCurrentUser,
        getSource,
        canChange,
        setUser,
    };
})();
