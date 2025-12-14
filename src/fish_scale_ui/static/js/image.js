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

        // Initial zoom to fit
        zoomToFit();

        // Refresh log after image loads
        window.app.loadLog();
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

        currentZoom = Math.min(scaleX, scaleY, 1) * 0.95; // 95% to leave small margin
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

    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', init);

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
        getCurrentZoom
    };
})();
