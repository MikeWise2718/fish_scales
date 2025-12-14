/**
 * Fish Scale Measurement UI - Settings Management
 * Handles loading/saving user preferences to localStorage
 */

window.settings = (function() {
    const STORAGE_KEY = 'fishScaleSettings';

    // Default settings
    const defaults = {
        scrollWheelZoom: true,
        showOverlayGrid: false,
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

        // Show overlay grid checkbox
        const showOverlayGridEl = document.getElementById('showOverlayGrid');
        if (showOverlayGridEl) {
            showOverlayGridEl.addEventListener('change', function() {
                set('showOverlayGrid', this.checked);
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

        // Show overlay grid
        const showOverlayGridEl = document.getElementById('showOverlayGrid');
        if (showOverlayGridEl) {
            showOverlayGridEl.checked = current.showOverlayGrid;
        }
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
