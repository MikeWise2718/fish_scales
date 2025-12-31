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
                    detailsCell.innerHTML = formatLogDetails(entry.details);

                    row.appendChild(timeCell);
                    row.appendChild(eventCell);
                    row.appendChild(detailsCell);
                    tbody.appendChild(row);
                });
            })
            .catch(err => console.error('Failed to load log:', err));
    }

    // Format log entry details, highlighting hexagonalness when present
    function formatLogDetails(details) {
        if (!details || Object.keys(details).length === 0) {
            return '';
        }

        const parts = [];
        const hexScore = details.hexagonalness_score;
        const reliability = details.reliability;

        // Process all details except hexagonalness-related ones first
        for (const [key, value] of Object.entries(details)) {
            if (key === 'hexagonalness_score' || key === 'reliability') {
                continue;  // Handle separately
            }
            parts.push(`${key}: ${value}`);
        }

        // Add hexagonalness with special formatting if present
        if (hexScore !== undefined && hexScore !== null) {
            const scoreNum = parseFloat(hexScore);
            let scoreClass = 'score-poor';
            if (scoreNum >= 0.7) {
                scoreClass = 'score-good';
            } else if (scoreNum >= 0.4) {
                scoreClass = 'score-medium';
            }

            let hexText = `<span class="log-hex">Hex: <span class="log-hex-score ${scoreClass}">${scoreNum.toFixed(3)}</span>`;
            if (reliability && reliability !== 'high') {
                hexText += ` <span class="log-hex-reliability">(${reliability})</span>`;
            }
            hexText += '</span>';
            parts.push(hexText);
        }

        return parts.join(', ');
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
                // Cancel edit mode, then clear multi-selection, then clear single selection
                if (window.editor?.getMode() !== 'none') {
                    window.editor.cancelMode();
                } else if (window.overlay?.hasMultiSelection()) {
                    window.overlay.clearMultiSelection();
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

            // Arrow keys - in chain mode, navigate the DAG
            if (window.editor?.getMode() === window.editor?.EditMode?.ADD_CHAIN) {
                if (e.key === 'ArrowLeft') {
                    e.preventDefault();
                    window.editor.chainGoBack();
                    return;
                }
                if (e.key === 'ArrowRight') {
                    e.preventDefault();
                    window.editor.chainGoForward();
                    return;
                }
                if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    window.editor.chainCyclePrev();
                    return;
                }
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    window.editor.chainCycleNext();
                    return;
                }
            }

            // Delete / Backspace - delete selected item(s)
            if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault();
                if (window.overlay?.hasMultiSelection()) {
                    window.editor?.deleteMultiSelected();
                } else {
                    window.editor?.deleteSelected();
                }
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

            // Ctrl+N - New set
            if (e.ctrlKey && e.key === 'n') {
                e.preventDefault();
                document.getElementById('addSetBtn')?.click();
                return;
            }

            // Ctrl+1-9 - Switch to set 1-9
            if (e.ctrlKey && e.key >= '1' && e.key <= '9') {
                e.preventDefault();
                const setIndex = parseInt(e.key) - 1;
                const setList = window.sets?.getSetList() || [];
                if (setIndex < setList.length) {
                    window.sets?.switchSet(setList[setIndex].id);
                }
                return;
            }

            // Ctrl+S to save - handled by extraction.js

            // F1 or ? - Open keyboard shortcuts help
            if (e.key === 'F1' || (e.key === '?' && !e.ctrlKey)) {
                e.preventDefault();
                window.open('/static/help/shortcuts.html', 'shortcuts', 'width=800,height=700');
                return;
            }

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
