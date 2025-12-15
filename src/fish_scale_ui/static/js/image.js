/**
 * Fish Scale Measurement UI - Image Viewer
 * Handles image display, zoom, pan, and rotation
 */

window.imageViewer = (function() {
    // State
    let currentZoom = 1;
    let isPanning = false;
    let panStart = { x: 0, y: 0 };
    let scrollStart = { x: 0, y: 0 };
    let imageUrl = null;

    // Crop state
    let isCropping = false;
    let cropStart = null;
    let cropEnd = null;
    let cropCanvas = null;
    let cropCtx = null;

    // Constants
    const MIN_ZOOM = 0.1;
    const MAX_ZOOM = 10;
    const ZOOM_STEP = 0.25;

    // DOM elements
    let container, wrapper, image, canvas, zoomDisplay;

    function init() {
        container = document.getElementById('imageContainer');
        wrapper = document.getElementById('imageWrapper');
        image = document.getElementById('mainImage');
        canvas = document.getElementById('overlayCanvas');
        zoomDisplay = document.getElementById('zoomLevel');

        // Mouse wheel zoom
        container.addEventListener('wheel', handleWheel, { passive: false });

        // Pan with mouse drag
        container.addEventListener('mousedown', handleMouseDown);
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);

        // Image load event
        image.addEventListener('load', handleImageLoad);
    }

    function loadImage(url) {
        imageUrl = url;
        image.src = url;
        image.style.display = 'block';
    }

    function handleImageLoad() {
        // Resize canvas to match image
        canvas.width = image.naturalWidth;
        canvas.height = image.naturalHeight;

        // Resize overlay canvas if available
        if (window.overlay) {
            window.overlay.resize(image.naturalWidth, image.naturalHeight);
        }

        // Initial zoom to fit
        zoomToFit();

        // Refresh log after image loads
        window.app.loadLog();

        // Dispatch imageLoaded event for other modules
        document.dispatchEvent(new CustomEvent('imageLoaded', {
            detail: {
                width: image.naturalWidth,
                height: image.naturalHeight,
            }
        }));
    }

    function handleWheel(e) {
        // Check if scroll wheel zoom is enabled
        if (window.settings && !window.settings.get('scrollWheelZoom')) {
            // Allow normal scrolling when zoom is disabled
            return;
        }

        e.preventDefault();

        // Calculate zoom change
        const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
        const newZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, currentZoom + delta));

        if (newZoom === currentZoom) return;

        // Get mouse position relative to container
        const rect = container.getBoundingClientRect();
        const mouseX = e.clientX - rect.left + container.scrollLeft;
        const mouseY = e.clientY - rect.top + container.scrollTop;

        // Calculate position in image coordinates before zoom
        const imgX = mouseX / currentZoom;
        const imgY = mouseY / currentZoom;

        // Apply new zoom
        currentZoom = newZoom;
        applyZoom();

        // Calculate new scroll position to keep mouse point fixed
        const newMouseX = imgX * currentZoom;
        const newMouseY = imgY * currentZoom;

        container.scrollLeft = newMouseX - (e.clientX - rect.left);
        container.scrollTop = newMouseY - (e.clientY - rect.top);
    }

    function handleMouseDown(e) {
        // Only pan with left mouse button and not in special modes
        if (e.button !== 0) return;
        if (container.classList.contains('measuring')) return;
        if (container.classList.contains('cropping')) return;

        isPanning = true;
        container.style.cursor = 'grabbing';
        panStart.x = e.clientX;
        panStart.y = e.clientY;
        scrollStart.x = container.scrollLeft;
        scrollStart.y = container.scrollTop;
    }

    function handleMouseMove(e) {
        if (!isPanning) return;

        const dx = e.clientX - panStart.x;
        const dy = e.clientY - panStart.y;

        container.scrollLeft = scrollStart.x - dx;
        container.scrollTop = scrollStart.y - dy;
    }

    function handleMouseUp() {
        if (isPanning) {
            isPanning = false;
            container.style.cursor = '';
        }
    }

    function applyZoom() {
        wrapper.style.transform = `scale(${currentZoom})`;
        zoomDisplay.textContent = Math.round(currentZoom * 100) + '%';
    }

    function zoomIn() {
        currentZoom = Math.min(MAX_ZOOM, currentZoom + ZOOM_STEP);
        applyZoom();
    }

    function zoomOut() {
        currentZoom = Math.max(MIN_ZOOM, currentZoom - ZOOM_STEP);
        applyZoom();
    }

    function zoomToFit() {
        if (!image.naturalWidth || !image.naturalHeight) return;

        const containerRect = container.getBoundingClientRect();
        const scaleX = containerRect.width / image.naturalWidth;
        const scaleY = containerRect.height / image.naturalHeight;

        // Scale to fit container (allow scaling up for small images)
        currentZoom = Math.min(scaleX, scaleY) * 0.95; // 95% to leave small margin
        currentZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, currentZoom)); // Clamp to valid range
        applyZoom();

        // Center the image
        container.scrollLeft = 0;
        container.scrollTop = 0;
    }

    function setZoom(level) {
        currentZoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, level));
        applyZoom();
    }

    function rotate(direction) {
        if (!imageUrl) return;

        // Check for unsaved changes
        if (window.extraction?.checkDirty()) {
            showRotateWarning(direction);
            return;
        }

        performRotation(direction);
    }

    function showRotateWarning(direction) {
        window.app.showModal(
            'Unsaved Changes',
            '<p>You have unsaved overlay changes. Rotating the image will save the rotated image to disk.</p><p>Do you want to save your overlay first?</p>',
            [
                { text: 'Cancel', action: () => {} },
                { text: 'Rotate without Saving', action: () => performRotation(direction) },
                { text: 'Save & Rotate', primary: true, action: async () => {
                    const saved = await window.extraction.saveSlo();
                    if (saved) {
                        performRotation(direction);
                    }
                }},
            ]
        );
    }

    function performRotation(direction) {
        fetch('/api/rotate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ direction })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                window.app.showToast(data.error, 'error');
            } else {
                // Reload image with cache buster
                image.src = data.url;
                window.app.showToast('Image rotated', 'success');
                window.app.loadLog();

                // Clear overlay data after rotation (coordinates no longer valid)
                if (window.overlay) {
                    window.overlay.clear();
                }
                if (window.data) {
                    window.data.clear();
                }
                if (window.editor) {
                    window.editor.setData([], []);
                }
                if (window.undoManager) {
                    window.undoManager.clear();
                }
            }
        })
        .catch(err => {
            window.app.showToast('Failed to rotate: ' + err.message, 'error');
        });
    }

    function getImageDimensions() {
        return {
            width: image.naturalWidth,
            height: image.naturalHeight
        };
    }

    function getCanvas() {
        return canvas;
    }

    function getContainer() {
        return container;
    }

    function getCurrentZoom() {
        return currentZoom;
    }

    // Crop functionality
    function initCrop() {
        const cropBtn = document.getElementById('cropBtn');
        const cropConfirmBtn = document.getElementById('cropConfirmBtn');
        const cropCancelBtn = document.getElementById('cropCancelBtn');
        const autocropBtn = document.getElementById('autocropBtn');

        if (cropBtn) {
            cropBtn.addEventListener('click', startCrop);
        }
        if (cropConfirmBtn) {
            cropConfirmBtn.addEventListener('click', confirmCrop);
        }
        if (cropCancelBtn) {
            cropCancelBtn.addEventListener('click', cancelCrop);
        }
        if (autocropBtn) {
            autocropBtn.addEventListener('click', autocrop);
        }
    }

    function autocrop() {
        if (!image.src || image.style.display === 'none') {
            window.app.showToast('No image loaded', 'error');
            return;
        }

        // Disable button during operation
        const autocropBtn = document.getElementById('autocropBtn');
        if (autocropBtn) {
            autocropBtn.disabled = true;
            autocropBtn.textContent = 'Processing...';
        }

        fetch('/api/autocrop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                window.app.showToast(data.error, 'warning');
            } else {
                // Reload image with cache buster
                image.src = data.url;
                window.app.showToast('Image autocropped', 'success');
                window.app.loadLog();

                // Clear overlay data
                if (window.overlay) {
                    window.overlay.clear();
                }
                if (window.data) {
                    window.data.clear();
                }
            }
        })
        .catch(err => {
            window.app.showToast('Autocrop failed: ' + err.message, 'error');
        })
        .finally(() => {
            // Re-enable button
            if (autocropBtn) {
                autocropBtn.disabled = false;
                autocropBtn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2"/>
                        <path d="M9 9h6v6H9z"/>
                    </svg>
                    Autocrop
                `;
            }
        });
    }

    // Track crop click state: 0 = waiting for first click, 1 = waiting for second click, 2 = selection complete
    let cropClickState = 0;

    function startCrop() {
        if (!image.src || image.style.display === 'none') {
            window.app.showToast('No image loaded', 'error');
            return;
        }

        isCropping = true;
        cropClickState = 0;
        cropStart = null;
        cropEnd = null;

        // Create crop canvas if not exists
        if (!cropCanvas) {
            cropCanvas = document.createElement('canvas');
            cropCanvas.id = 'cropCanvas';
            cropCanvas.style.cssText = 'position: absolute; top: 0; left: 0; pointer-events: none;';
            wrapper.appendChild(cropCanvas);
        }
        cropCanvas.width = image.naturalWidth;
        cropCanvas.height = image.naturalHeight;
        cropCanvas.style.display = 'block';
        cropCtx = cropCanvas.getContext('2d');

        // Update UI
        container.classList.add('cropping');
        document.getElementById('cropStatus').textContent = 'Click to set first corner...';
        document.getElementById('cropBtn').disabled = true;
        document.getElementById('cropActionButtons').style.display = 'none';

        // Add event listeners
        container.addEventListener('click', handleCropClick);
        document.addEventListener('mousemove', handleCropMouseMove);
        document.addEventListener('keydown', handleCropEscape);
    }

    function handleCropClick(e) {
        if (!isCropping) return;
        if (e.button !== 0) return; // Left button only

        const rect = container.getBoundingClientRect();
        const x = (e.clientX - rect.left + container.scrollLeft) / currentZoom;
        const y = (e.clientY - rect.top + container.scrollTop) / currentZoom;

        if (cropClickState === 0) {
            // First click - set start corner
            cropStart = { x, y };
            cropEnd = { x, y };
            cropClickState = 1;
            document.getElementById('cropStatus').textContent = 'Click to set second corner...';
            drawCropOverlay();
        } else if (cropClickState === 1) {
            // Second click - set end corner
            cropEnd = { x, y };
            cropClickState = 2;

            // Calculate crop region
            const region = getCropRegion();
            if (region && region.width > 10 && region.height > 10) {
                // Valid crop region
                document.getElementById('cropStatus').textContent =
                    `Selected: ${Math.round(region.width)} x ${Math.round(region.height)} px`;
                document.getElementById('cropActionButtons').style.display = 'flex';
            } else {
                document.getElementById('cropStatus').textContent = 'Selection too small. Starting over...';
                // Reset to allow new selection
                cropClickState = 0;
                cropStart = null;
                cropEnd = null;
                setTimeout(() => {
                    if (isCropping) {
                        document.getElementById('cropStatus').textContent = 'Click to set first corner...';
                    }
                }, 1500);
            }
            drawCropOverlay();
        }
    }

    function handleCropMouseMove(e) {
        // Only show preview when waiting for second click
        if (!isCropping || cropClickState !== 1 || !cropStart) return;

        const rect = container.getBoundingClientRect();
        const x = (e.clientX - rect.left + container.scrollLeft) / currentZoom;
        const y = (e.clientY - rect.top + container.scrollTop) / currentZoom;

        cropEnd = { x, y };
        drawCropOverlay();
    }

    function handleCropEscape(e) {
        if (e.key === 'Escape' && isCropping) {
            cancelCrop();
        }
    }

    function getCropRegion() {
        if (!cropStart || !cropEnd) return null;

        const x = Math.min(cropStart.x, cropEnd.x);
        const y = Math.min(cropStart.y, cropEnd.y);
        const width = Math.abs(cropEnd.x - cropStart.x);
        const height = Math.abs(cropEnd.y - cropStart.y);

        // Clamp to image bounds
        const clampedX = Math.max(0, Math.min(x, image.naturalWidth));
        const clampedY = Math.max(0, Math.min(y, image.naturalHeight));
        const clampedWidth = Math.min(width, image.naturalWidth - clampedX);
        const clampedHeight = Math.min(height, image.naturalHeight - clampedY);

        return {
            x: Math.round(clampedX),
            y: Math.round(clampedY),
            width: Math.round(clampedWidth),
            height: Math.round(clampedHeight)
        };
    }

    function drawCropOverlay() {
        if (!cropCtx || !cropCanvas) return;

        cropCtx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);

        if (!cropStart || !cropEnd) return;

        const region = getCropRegion();
        if (!region) return;

        // Draw semi-transparent overlay on areas outside crop
        cropCtx.fillStyle = 'rgba(0, 0, 0, 0.5)';

        // Top
        cropCtx.fillRect(0, 0, cropCanvas.width, region.y);
        // Bottom
        cropCtx.fillRect(0, region.y + region.height, cropCanvas.width, cropCanvas.height - region.y - region.height);
        // Left
        cropCtx.fillRect(0, region.y, region.x, region.height);
        // Right
        cropCtx.fillRect(region.x + region.width, region.y, cropCanvas.width - region.x - region.width, region.height);

        // Draw crop border
        cropCtx.strokeStyle = '#ffffff';
        cropCtx.lineWidth = 2;
        cropCtx.setLineDash([5, 5]);
        cropCtx.strokeRect(region.x, region.y, region.width, region.height);
        cropCtx.setLineDash([]);

        // Draw corner handles
        const handleSize = 8;
        cropCtx.fillStyle = '#ffffff';
        cropCtx.fillRect(region.x - handleSize/2, region.y - handleSize/2, handleSize, handleSize);
        cropCtx.fillRect(region.x + region.width - handleSize/2, region.y - handleSize/2, handleSize, handleSize);
        cropCtx.fillRect(region.x - handleSize/2, region.y + region.height - handleSize/2, handleSize, handleSize);
        cropCtx.fillRect(region.x + region.width - handleSize/2, region.y + region.height - handleSize/2, handleSize, handleSize);
    }

    function confirmCrop() {
        const region = getCropRegion();
        if (!region || region.width < 10 || region.height < 10) {
            window.app.showToast('Invalid crop selection', 'error');
            return;
        }

        // Send crop request to server
        fetch('/api/crop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(region)
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                window.app.showToast(data.error, 'error');
            } else {
                // Reload image with cache buster
                image.src = data.url;
                window.app.showToast('Image cropped', 'success');
                window.app.loadLog();

                // Clear overlay data
                if (window.overlay) {
                    window.overlay.clear();
                }
                if (window.data) {
                    window.data.clear();
                }
            }
            cleanupCrop();
        })
        .catch(err => {
            window.app.showToast('Failed to crop: ' + err.message, 'error');
            cleanupCrop();
        });
    }

    function cancelCrop() {
        cleanupCrop();
        window.app.showToast('Crop cancelled', 'info');
    }

    function cleanupCrop() {
        isCropping = false;
        cropClickState = 0;
        cropStart = null;
        cropEnd = null;

        // Hide crop canvas
        if (cropCanvas) {
            cropCanvas.style.display = 'none';
            if (cropCtx) {
                cropCtx.clearRect(0, 0, cropCanvas.width, cropCanvas.height);
            }
        }

        // Remove event listeners
        container.removeEventListener('click', handleCropClick);
        document.removeEventListener('mousemove', handleCropMouseMove);
        document.removeEventListener('keydown', handleCropEscape);

        // Update UI
        container.classList.remove('cropping');
        document.getElementById('cropStatus').textContent = '';
        document.getElementById('cropBtn').disabled = false;
        document.getElementById('cropActionButtons').style.display = 'none';
    }

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        init();
        initCrop();
    });

    return {
        loadImage,
        zoomIn,
        zoomOut,
        zoomToFit,
        setZoom,
        rotate,
        getImageDimensions,
        getCanvas,
        getContainer,
        getCurrentZoom,
        startCrop,
        cancelCrop
    };
})();
