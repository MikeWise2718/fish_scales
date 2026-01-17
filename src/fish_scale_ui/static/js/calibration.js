/**
 * Fish Scale Measurement UI - Calibration System
 */

window.calibration = (function() {
    // State
    let isDrawing = false;
    let startPoint = null;
    let endPoint = null;
    let currentCalibration = null;

    // DOM elements
    let valueDisplay, methodBadge, scaleUmInput, scalePxInput;
    let umPerPxInput, measureBtn, measureStatus;

    function init() {
        valueDisplay = document.getElementById('calibrationValue');
        methodBadge = document.getElementById('calibrationMethod');
        scaleUmInput = document.getElementById('scaleUm');
        scalePxInput = document.getElementById('scalePx');
        umPerPxInput = document.getElementById('umPerPx');
        measureBtn = document.getElementById('measureScaleBtn');
        measureStatus = document.getElementById('measureStatus');

        // Scale bar input apply
        document.getElementById('applyCalibrationBtn').addEventListener('click', () => {
            const um = parseFloat(scaleUmInput.value);
            const px = parseFloat(scalePxInput.value);

            if (!um || !px || um <= 0 || px <= 0) {
                window.app.showToast('Enter valid scale bar values', 'error');
                return;
            }

            applyCalibration(um / px, 'scale_bar');
        });

        // Direct input apply
        document.getElementById('applyDirectBtn').addEventListener('click', () => {
            const umPerPx = parseFloat(umPerPxInput.value);

            if (!umPerPx || umPerPx <= 0) {
                window.app.showToast('Enter a valid calibration value', 'error');
                return;
            }

            applyCalibration(umPerPx, 'direct');
        });

        // Measure scale bar button
        measureBtn.addEventListener('click', startMeasuring);

        // Apply estimate button
        const applyEstimateBtn = document.getElementById('applyEstimateBtn');
        if (applyEstimateBtn) {
            applyEstimateBtn.addEventListener('click', () => {
                // Apply the auto-estimated calibration (0.14 µm/pixel for 700x magnification)
                applyCalibration(0.14, 'estimate');
            });
        }

        // Load current calibration
        loadCalibration();
    }

    function loadCalibration() {
        fetch('/api/calibration')
            .then(response => response.json())
            .then(data => {
                if (data.calibration) {
                    currentCalibration = data.calibration;
                    updateDisplay();
                    // Notify other modules that calibration changed
                    document.dispatchEvent(new CustomEvent('calibrationChanged', {
                        detail: { calibration: currentCalibration }
                    }));
                } else {
                    displayAutoEstimate();
                }
            })
            .catch(err => {
                console.error('Failed to load calibration:', err);
                displayAutoEstimate();
            });
    }

    function applyCalibration(umPerPx, method) {
        fetch('/api/calibration', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ um_per_px: umPerPx, method })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                window.app.showToast(data.error, 'error');
            } else {
                currentCalibration = data.calibration;
                updateDisplay();
                window.app.showToast('Calibration applied', 'success');
                window.app.loadLog();
                // Mark state as dirty - calibration is saved in annotations
                window.extraction?.markDirty();
                // Notify other modules that calibration changed
                document.dispatchEvent(new CustomEvent('calibrationChanged', {
                    detail: { calibration: currentCalibration }
                }));
            }
        })
        .catch(err => {
            window.app.showToast('Failed to apply calibration: ' + err.message, 'error');
        });
    }

    function updateDisplay() {
        if (currentCalibration) {
            const umPerPx = currentCalibration.um_per_px;
            const method = currentCalibration.method || 'unknown';
            valueDisplay.textContent = `${umPerPx.toFixed(4)} µm/pixel`;

            // Show method badge with appropriate styling
            updateMethodBadge(method);

            // Also update input fields
            if (umPerPxInput) {
                umPerPxInput.value = umPerPx.toFixed(4);
            }

            // Re-render overlay in case calibration scale is shown
            if (window.overlay && window.overlay.render) {
                window.overlay.render();
            }
        }
    }

    function updateMethodBadge(method) {
        if (!methodBadge) return;

        // Remove all method classes
        methodBadge.classList.remove('method-estimate', 'method-manual', 'method-not-set');
        methodBadge.style.display = 'inline-block';

        switch (method) {
            case 'estimate':
                methodBadge.textContent = 'Estimated';
                methodBadge.classList.add('method-estimate');
                methodBadge.title = 'Using default 0.14 µm/pixel estimate - may be inaccurate';
                break;
            case 'scale_bar':
            case 'direct':
                methodBadge.textContent = 'Manual';
                methodBadge.classList.add('method-manual');
                methodBadge.title = 'Calibration set manually';
                break;
            case 'measure':
                methodBadge.textContent = 'Measured';
                methodBadge.classList.add('method-manual');
                methodBadge.title = 'Calibration measured from scale bar in image';
                break;
            case 'loaded':
                methodBadge.textContent = 'Loaded';
                methodBadge.classList.add('method-manual');
                methodBadge.title = 'Calibration loaded from saved annotations';
                break;
            default:
                methodBadge.style.display = 'none';
        }
    }

    function displayAutoEstimate() {
        // No calibration set - show default estimate with warning
        valueDisplay.textContent = '~0.14 µm/pixel';
        if (methodBadge) {
            methodBadge.textContent = 'Not Set';
            methodBadge.classList.remove('method-estimate', 'method-manual');
            methodBadge.classList.add('method-not-set');
            methodBadge.style.display = 'inline-block';
            methodBadge.title = 'No calibration set - using default estimate. Click ? for help.';
        }
    }

    function startMeasuring() {
        isDrawing = true;
        startPoint = null;
        endPoint = null;

        const container = window.imageViewer.getContainer();
        container.classList.add('measuring');

        measureStatus.textContent = 'Click first point on scale bar...';
        measureBtn.disabled = true;

        // Add click handlers
        container.addEventListener('click', handleMeasureClick);

        // Add escape to cancel
        document.addEventListener('keydown', handleEscapeKey);
    }

    function handleMeasureClick(e) {
        const container = window.imageViewer.getContainer();
        const zoom = window.imageViewer.getCurrentZoom();

        // Get click position in image coordinates
        const rect = container.getBoundingClientRect();
        const x = (e.clientX - rect.left + container.scrollLeft) / zoom;
        const y = (e.clientY - rect.top + container.scrollTop) / zoom;

        if (!startPoint) {
            startPoint = { x, y };
            measureStatus.textContent = 'Click second point on scale bar...';
            drawMeasureLine();
        } else {
            endPoint = { x, y };
            finishMeasuring();
        }
    }

    function handleEscapeKey(e) {
        if (e.key === 'Escape' && isDrawing) {
            cancelMeasuring();
        }
    }

    function drawMeasureLine() {
        const canvas = window.imageViewer.getCanvas();
        const ctx = canvas.getContext('2d');

        // Clear previous drawing
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (startPoint) {
            // Draw start point
            ctx.fillStyle = '#00ffff';
            ctx.beginPath();
            ctx.arc(startPoint.x, startPoint.y, 5, 0, Math.PI * 2);
            ctx.fill();

            if (endPoint) {
                // Draw end point
                ctx.beginPath();
                ctx.arc(endPoint.x, endPoint.y, 5, 0, Math.PI * 2);
                ctx.fill();

                // Draw line
                ctx.strokeStyle = '#00ffff';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(startPoint.x, startPoint.y);
                ctx.lineTo(endPoint.x, endPoint.y);
                ctx.stroke();
            }
        }
    }

    function finishMeasuring() {
        isDrawing = false;

        const container = window.imageViewer.getContainer();
        container.classList.remove('measuring');
        container.removeEventListener('click', handleMeasureClick);
        document.removeEventListener('keydown', handleEscapeKey);

        measureBtn.disabled = false;

        // Calculate distance in pixels
        const dx = endPoint.x - startPoint.x;
        const dy = endPoint.y - startPoint.y;
        const pixelDistance = Math.sqrt(dx * dx + dy * dy);

        measureStatus.textContent = `Distance: ${pixelDistance.toFixed(1)} pixels`;

        // Update pixel input and prompt for µm value
        scalePxInput.value = pixelDistance.toFixed(1);
        scaleUmInput.focus();

        drawMeasureLine();

        window.app.showToast('Enter the scale bar length in µm and click Apply', 'info');
    }

    function cancelMeasuring() {
        isDrawing = false;

        const container = window.imageViewer.getContainer();
        container.classList.remove('measuring');
        container.removeEventListener('click', handleMeasureClick);
        document.removeEventListener('keydown', handleEscapeKey);

        measureBtn.disabled = false;
        measureStatus.textContent = '';

        // Clear canvas
        const canvas = window.imageViewer.getCanvas();
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    function getCalibration() {
        return currentCalibration;
    }

    function getCurrentCalibration() {
        return currentCalibration;
    }

    function setCalibration(calibrationData) {
        // Set calibration from loaded annotations data
        if (calibrationData && calibrationData.um_per_px) {
            currentCalibration = { ...calibrationData };
            // If no method specified, mark as loaded from file
            if (!currentCalibration.method) {
                currentCalibration.method = 'loaded';
            }
            updateDisplay();
            // Notify other modules that calibration changed
            document.dispatchEvent(new CustomEvent('calibrationChanged', {
                detail: { calibration: currentCalibration }
            }));
        }
    }

    function pxToUm(pixels) {
        if (!currentCalibration) return pixels * 0.14; // Auto-estimate
        return pixels * currentCalibration.um_per_px;
    }

    function umToPx(um) {
        if (!currentCalibration) return um / 0.14; // Auto-estimate
        return um / currentCalibration.um_per_px;
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        loadCalibration,
        getCalibration,
        getCurrentCalibration,
        setCalibration,
        pxToUm,
        umToPx
    };
})();
