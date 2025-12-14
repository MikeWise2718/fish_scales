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

        // Rotate buttons
        document.getElementById('rotateLeftBtn').addEventListener('click', () => {
            window.imageViewer.rotate('left');
        });

        document.getElementById('rotateRightBtn').addEventListener('click', () => {
            window.imageViewer.rotate('right');
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

        // Save SLO button (placeholder for Phase 2)
        document.getElementById('saveSloBtn').addEventListener('click', () => {
            showToast('Save SLO coming in Phase 2', 'warning');
        });
    }

    // Keyboard shortcuts
    function initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Skip if focused on input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            // Zoom shortcuts
            if (e.key === '+' || e.key === '=') {
                e.preventDefault();
                window.imageViewer.zoomIn();
            } else if (e.key === '-') {
                e.preventDefault();
                window.imageViewer.zoomOut();
            } else if (e.key === '0') {
                e.preventDefault();
                window.imageViewer.zoomToFit();
            }

            // Ctrl+S to save
            if (e.ctrlKey && e.key === 's') {
                e.preventDefault();
                showToast('Save SLO coming in Phase 2', 'warning');
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
