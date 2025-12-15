/**
 * Fish Scale Measurement UI - Main Application
 */

window.app = (function() {
    // Tab management
    function initTabs() {
        const headers = document.querySelectorAll('.tab-header');
        const panes = document.querySelectorAll('.tab-pane');

        headers.forEach(header => {
            header.addEventListener('click', () => {
                const tabName = header.dataset.tab;

                // Update headers
                headers.forEach(h => h.classList.remove('active'));
                header.classList.add('active');

                // Update panes
                panes.forEach(p => {
                    p.classList.toggle('active', p.dataset.tab === tabName);
                });
            });
        });
    }

    // Toast notifications
    function showToast(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 200);
        }, 3000);
    }

    // Modal dialogs
    function showModal(title, body, buttons) {
        const overlay = document.getElementById('modalOverlay');
        const modal = document.getElementById('modal');
        const headerEl = document.getElementById('modalHeader');
        const bodyEl = document.getElementById('modalBody');
        const footerEl = document.getElementById('modalFooter');

        headerEl.textContent = title;
        bodyEl.innerHTML = body;
        footerEl.innerHTML = '';

        buttons.forEach(btn => {
            const button = document.createElement('button');
            button.className = `btn ${btn.primary ? 'btn-primary' : 'btn-secondary'}`;
            button.textContent = btn.text;
            button.addEventListener('click', () => {
                overlay.style.display = 'none';
                if (btn.action) btn.action();
            });
            footerEl.appendChild(button);
        });

        overlay.style.display = 'flex';
    }

    function hideModal() {
        document.getElementById('modalOverlay').style.display = 'none';
    }

    // Log loading
    function loadLog() {
        fetch('/api/log')
            .then(response => response.json())
            .then(data => {
                const tbody = document.getElementById('logBody');
                tbody.innerHTML = '';

                data.entries.forEach(entry => {
                    const row = document.createElement('tr');

                    const timeCell = document.createElement('td');
                    const time = new Date(entry.timestamp);
                    timeCell.textContent = time.toLocaleTimeString();

                    const eventCell = document.createElement('td');
                    eventCell.textContent = entry.event_type.replace(/_/g, ' ');

                    const detailsCell = document.createElement('td');
                    const details = Object.entries(entry.details || {})
                        .map(([k, v]) => `${k}: ${v}`)
                        .join(', ');
                    detailsCell.textContent = details;

                    row.appendChild(timeCell);
                    row.appendChild(eventCell);
                    row.appendChild(detailsCell);
                    tbody.appendChild(row);
                });
            })
            .catch(err => console.error('Failed to load log:', err));
    }

    // Toolbar buttons
    function initToolbar() {
        // New Image button
        document.getElementById('newImageBtn').addEventListener('click', () => {
            window.location.href = '/';
        });

        // Zoom buttons
        document.getElementById('zoomInBtn').addEventListener('click', () => {
            window.imageViewer.zoomIn();
        });

        document.getElementById('zoomOutBtn').addEventListener('click', () => {
            window.imageViewer.zoomOut();
        });

        document.getElementById('zoomFitBtn').addEventListener('click', () => {
            window.imageViewer.zoomToFit();
        });

        // Image tab rotate buttons
        const rotateLeftBtnTab = document.getElementById('rotateLeftBtnTab');
        if (rotateLeftBtnTab) {
            rotateLeftBtnTab.addEventListener('click', () => {
                window.imageViewer.rotate('left');
            });
        }

        const rotateRightBtnTab = document.getElementById('rotateRightBtnTab');
        if (rotateRightBtnTab) {
            rotateRightBtnTab.addEventListener('click', () => {
                window.imageViewer.rotate('right');
            });
        }

        // Save SLO button - handled by extraction.js
    }

    // Keyboard shortcuts
    function initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Skip if focused on input (except for Escape)
            const isInputFocused = e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA';

            // Escape key - always handle (cancel mode, deselect, exit input)
            if (e.key === 'Escape') {
                e.preventDefault();
                if (isInputFocused) {
                    e.target.blur();
                    return;
                }
                // Cancel edit mode or deselect
                if (window.editor?.getMode() !== 'none') {
                    window.editor.cancelMode();
                } else {
                    window.overlay?.deselect();
                }
                return;
            }

            // Skip other shortcuts if focused on input
            if (isInputFocused) {
                return;
            }

            // Zoom shortcuts
            if (e.key === '+' || e.key === '=') {
                e.preventDefault();
                window.imageViewer.zoomIn();
                return;
            }
            if (e.key === '-') {
                e.preventDefault();
                window.imageViewer.zoomOut();
                return;
            }
            if (e.key === '0') {
                e.preventDefault();
                window.imageViewer.zoomToFit();
                return;
            }

            // Delete / Backspace - delete selected item
            if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault();
                window.editor?.deleteSelected();
                return;
            }

            // Tab - cycle through selection
            if (e.key === 'Tab') {
                e.preventDefault();
                window.editor?.cycleSelection();
                return;
            }

            // Ctrl+Z - Undo
            if (e.ctrlKey && e.key === 'z') {
                e.preventDefault();
                window.undoManager?.undo();
                return;
            }

            // Ctrl+Y - Redo
            if (e.ctrlKey && e.key === 'y') {
                e.preventDefault();
                window.undoManager?.redo();
                return;
            }

            // Ctrl+S to save - handled by extraction.js

            // Arrow keys - nudge selected tubercle
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                window.editor?.nudgeSelected(0, -1);
                return;
            }
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                window.editor?.nudgeSelected(0, 1);
                return;
            }
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                window.editor?.nudgeSelected(-1, 0);
                return;
            }
            if (e.key === 'ArrowRight') {
                e.preventDefault();
                window.editor?.nudgeSelected(1, 0);
                return;
            }
        });
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', () => {
        initTabs();
        initToolbar();
        initKeyboardShortcuts();
    });

    return {
        showToast,
        showModal,
        hideModal,
        loadLog
    };
})();
