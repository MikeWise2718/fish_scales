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
    let valueDisplay, warningBadge, scaleUmInput, scalePxInput;
    let umPerPxInput, measureBtn, measureStatus;

    function init() {
        valueDisplay = document.getElementById('calibrationValue');
        warningBadge = document.getElementById('calibrationWarning');
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
            }
        })
        .catch(err => {
            window.app.showToast('Failed to apply calibration: ' + err.message, 'error');
        });
    }

    function updateDisplay() {
        if (currentCalibration) {
            const umPerPx = currentCalibration.um_per_px;
            valueDisplay.textContent = `${umPerPx.toFixed(4)} µm/pixel`;
            warningBadge.style.display = 'none';

            // Also update input fields
            umPerPxInput.value = umPerPx.toFixed(4);
        }
    }

    function displayAutoEstimate() {
        // Auto-estimation based on 700x magnification
        // Typical SEM at 700x: ~0.14 µm/pixel (varies by detector)
        valueDisplay.textContent = '~0.14 µm/pixel (estimated)';
        warningBadge.style.display = 'inline';
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
        pxToUm,
        umToPx
    };
})();
