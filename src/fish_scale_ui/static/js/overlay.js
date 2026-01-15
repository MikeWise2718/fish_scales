/**
 * Fish Scale Measurement UI - Overlay Rendering
 */

window.overlay = (function() {
    let canvas = null;
    let ctx = null;
    let tubercles = [];
    let edges = [];
    let debugShapes = [];
    let selectedTubId = null;
    let selectedEdgeIdx = null;
    let scale = 1;

    // Multi-selection state
    let selectedTubIds = new Set();
    let selectedEdgeIdxs = new Set();

    // Area selection state
    let isAreaSelecting = false;
    let areaSelectStart = null;  // {x, y} in image coords
    let areaSelectEnd = null;    // {x, y} in image coords

    // Highlighted edge for chain mode navigation preview
    let highlightedEdge = null;

    // Toggle state (controlled by checkboxes under image, independent of Settings)
    let toggleState = {
        numbers: false,    // Tube IDs
        tubes: true,
        itcIds: false,     // ITC IDs
        links: true,       // ITCs (connection lines)
        scale: false,
        grid: false,       // Coordinate grid
        ellipses: false
    };

    // Color mode for tubercles: 'source' (extracted vs manual), 'uniform' (all same color)
    // Future modes: 'neighbors' (by neighbor count), 'diameter' (by size), etc.
    let colorMode = 'source';

    // Get colors from settings (with defaults)
    function getColors() {
        const tubercleColor = (window.settings && window.settings.get('tubercleColor')) || '#00ffff';
        const manualTubercleColor = (window.settings && window.settings.get('manualTubercleColor')) || '#00ff00';
        const boundaryTubercleColor = (window.settings && window.settings.get('boundaryTubercleColor')) || '#ff8800';
        const connectionColor = (window.settings && window.settings.get('connectionColor')) || '#ffff00';
        return {
            tubercle: tubercleColor,           // Extracted tubercles (cyan)
            manualTubercle: manualTubercleColor, // Manually added (green)
            debugSeedTubercle: '#ff00ff',      // Debug seed tubercles (magenta)
            boundaryTubercle: boundaryTubercleColor, // Boundary nodes (orange)
            edge: connectionColor,
            selectedTubercle: '#ffff00', // Yellow for selection (changed from magenta)
            selectedEdge: '#ffff00',
            multiSelectedTubercle: '#ffff00',  // Yellow for multi-selection
            multiSelectedEdge: '#ffff00',
            highlightedEdge: '#ff8800',  // Orange for chain mode navigation preview
            areaSelectStroke: '#00ffff',  // Cyan for area selection rectangle
            areaSelectFill: 'rgba(0, 255, 255, 0.1)',
        };
    }

    // Get color for a specific tubercle based on color mode
    function getTubercleColor(tub, colors, isSelected) {
        if (isSelected) {
            return colors.selectedTubercle;
        }
        // Debug seeds always use magenta regardless of color mode
        if (tub.source === 'debug_seed') {
            return colors.debugSeedTubercle;
        }
        if (colorMode === 'source') {
            return tub.source === 'manual' ? colors.manualTubercle : colors.tubercle;
        }
        if (colorMode === 'boundary') {
            return tub.is_boundary ? colors.boundaryTubercle : colors.tubercle;
        }
        // Default/uniform mode
        return colors.tubercle;
    }

    // Set the color mode
    function setColorMode(mode) {
        colorMode = mode;
        render();
    }

    // Initialize toggle states from Settings defaults
    function initToggleStates() {
        // Get defaults from Settings (if available)
        if (window.settings) {
            toggleState.numbers = window.settings.get('showTubercleIds') || false;
            toggleState.scale = window.settings.get('showCalibrationScale') || false;
        }
        // tubes and links default to true (always shown unless toggled off)
        toggleState.tubes = true;
        toggleState.links = true;

        // Update checkbox UI to match
        updateToggleUI();
    }

    // Update toggle checkbox UI to match state
    function updateToggleUI() {
        const numbersEl = document.getElementById('toggleNumbers');
        const tubesEl = document.getElementById('toggleTubes');
        const linksEl = document.getElementById('toggleLinks');
        const scaleEl = document.getElementById('toggleScale');
        const gridEl = document.getElementById('toggleGrid');

        if (numbersEl) numbersEl.checked = toggleState.numbers;
        if (tubesEl) tubesEl.checked = toggleState.tubes;
        if (linksEl) linksEl.checked = toggleState.links;
        if (scaleEl) scaleEl.checked = toggleState.scale;
        if (gridEl) gridEl.checked = toggleState.grid;
    }

    // Bind toggle checkbox event handlers
    function bindToggleHandlers() {
        const numbersEl = document.getElementById('toggleNumbers');
        const tubesEl = document.getElementById('toggleTubes');
        const linksEl = document.getElementById('toggleLinks');
        const scaleEl = document.getElementById('toggleScale');
        const ellipsesEl = document.getElementById('showEllipses');

        if (numbersEl) {
            numbersEl.addEventListener('change', function() {
                toggleState.numbers = this.checked;
                render();
            });
        }
        if (tubesEl) {
            tubesEl.addEventListener('change', function() {
                toggleState.tubes = this.checked;
                render();
            });
        }
        if (linksEl) {
            linksEl.addEventListener('change', function() {
                toggleState.links = this.checked;
                render();
            });
        }
        if (scaleEl) {
            scaleEl.addEventListener('change', function() {
                toggleState.scale = this.checked;
                render();
            });
        }
        const gridEl = document.getElementById('toggleGrid');
        if (gridEl) {
            gridEl.addEventListener('change', function() {
                toggleState.grid = this.checked;
                render();
            });
        }
        if (ellipsesEl) {
            ellipsesEl.addEventListener('change', function() {
                toggleState.ellipses = this.checked;
                render();
            });
        }

        // ITC IDs checkbox
        const itcIdsEl = document.getElementById('toggleItcIds');
        if (itcIdsEl) {
            itcIdsEl.addEventListener('change', function() {
                toggleState.itcIds = this.checked;
                render();
            });
        }
    }

    // Initialize
    function init() {
        canvas = document.getElementById('overlayCanvas');
        if (!canvas) return;
        ctx = canvas.getContext('2d');

        // Make canvas interactive for Phase 2 click-to-select
        canvas.style.pointerEvents = 'auto';
        canvas.addEventListener('click', handleClick);

        // Bind toggle handlers
        bindToggleHandlers();

        // Initialize toggle states from Settings defaults
        initToggleStates();

        // Reset toggle states when new image is loaded
        document.addEventListener('imageLoaded', () => {
            initToggleStates();
        });
    }

    // Resize canvas to match image
    function resize(width, height) {
        if (!canvas) return;
        canvas.width = width;
        canvas.height = height;
        render();
    }

    // Set scale factor (for zoom)
    function setScale(newScale) {
        scale = newScale;
        render();
    }

    // Set debug shapes for visualization
    function setDebugShapes(shapes) {
        debugShapes = shapes || [];
        render();
    }

    // Set data (preserves selection if selected item still exists)
    function setData(newTubercles, newEdges, newDebugShapes) {
        tubercles = newTubercles || [];
        edges = newEdges || [];
        if (newDebugShapes !== undefined) {
            debugShapes = newDebugShapes || [];
        }

        // Preserve selection only if the selected item still exists in new data
        if (selectedTubId !== null) {
            const stillExists = tubercles.some(t => t.id === selectedTubId);
            if (!stillExists) {
                selectedTubId = null;
            }
        }
        if (selectedEdgeIdx !== null) {
            // Edge index may have changed, so clear it if out of bounds
            if (selectedEdgeIdx >= edges.length) {
                selectedEdgeIdx = null;
            }
        }

        // Clear multi-selection items that no longer exist
        const validTubIds = new Set(tubercles.map(t => t.id));
        selectedTubIds = new Set([...selectedTubIds].filter(id => validTubIds.has(id)));
        selectedEdgeIdxs = new Set([...selectedEdgeIdxs].filter(idx => idx < edges.length));

        render();
    }

    // Clear data
    function clear() {
        tubercles = [];
        edges = [];
        debugShapes = [];
        selectedTubId = null;
        selectedEdgeIdx = null;
        selectedTubIds.clear();
        selectedEdgeIdxs.clear();
        isAreaSelecting = false;
        areaSelectStart = null;
        areaSelectEnd = null;
        if (ctx && canvas) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    }

    // Render overlay
    function render() {
        if (!ctx || !canvas) return;

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const colors = getColors();

        // Draw edges (ITCs) if enabled
        if (toggleState.links) {
            edges.forEach((edge, idx) => {
                const isSelected = idx === selectedEdgeIdx;
                const isHighlighted = highlightedEdge &&
                    ((edge.id1 === highlightedEdge.id1 && edge.id2 === highlightedEdge.id2) ||
                     (edge.id1 === highlightedEdge.id2 && edge.id2 === highlightedEdge.id1));
                drawEdge(edge, isSelected, isHighlighted, colors);
            });
        }

        // Draw tubercles (TUBs) if enabled
        if (toggleState.tubes) {
            tubercles.forEach(tub => {
                const isSelected = tub.id === selectedTubId;
                drawTubercle(tub, isSelected, colors);
            });
        }

        // Draw Tube IDs if enabled (uses toggle state, not Settings)
        if (toggleState.numbers) {
            const fontSize = (window.settings && window.settings.get('idTextSize')) || 12;
            tubercles.forEach(tub => {
                drawTubercleId(tub, fontSize, colors);
            });
        }

        // Draw ITC IDs if enabled
        if (toggleState.itcIds) {
            const fontSize = (window.settings && window.settings.get('idTextSize')) || 12;
            edges.forEach((edge, idx) => {
                drawEdgeId(edge, idx, fontSize, colors);
            });
        }

        // Draw calibration scale if enabled (uses toggle state, not Settings)
        if (toggleState.scale) {
            drawCalibrationScale();
        }

        // Draw coordinate grid if enabled
        if (toggleState.grid) {
            drawCoordinateGrid();
        }

        // Draw debug shapes (always visible when present)
        if (debugShapes.length > 0) {
            drawDebugShapes(colors);
        }

        // Draw multi-selected tubercles (on top of regular tubercles)
        if (toggleState.tubes && selectedTubIds.size > 0) {
            selectedTubIds.forEach(id => {
                const tub = tubercles.find(t => t.id === id);
                if (tub) {
                    drawMultiSelectedTubercle(tub, colors);
                }
            });
        }

        // Draw multi-selected edges (on top of regular edges)
        if (toggleState.links && selectedEdgeIdxs.size > 0) {
            selectedEdgeIdxs.forEach(idx => {
                const edge = edges[idx];
                if (edge) {
                    drawMultiSelectedEdge(edge, colors);
                }
            });
        }

        // Draw area selection rectangle while dragging
        if (isAreaSelecting && areaSelectStart && areaSelectEnd) {
            drawAreaSelectionRect(areaSelectStart, areaSelectEnd, colors);
        }

        // Draw temporary region (auto-size feedback)
        if (temporaryRegion) {
            ctx.save();

            // Draw region rectangle
            ctx.strokeStyle = `rgba(255, 165, 0, ${temporaryRegion.opacity})`; // Orange
            ctx.fillStyle = `rgba(255, 165, 0, ${temporaryRegion.opacity * 0.15})`;
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.fillRect(temporaryRegion.x, temporaryRegion.y, temporaryRegion.width, temporaryRegion.height);
            ctx.strokeRect(temporaryRegion.x, temporaryRegion.y, temporaryRegion.width, temporaryRegion.height);

            // Draw all detected blobs
            ctx.setLineDash([]);
            if (temporaryRegion.allBlobs && temporaryRegion.allBlobs.length > 0) {
                temporaryRegion.allBlobs.forEach(blob => {
                    const isSelected = temporaryRegion.selectedBlob &&
                        Math.abs(blob.center_x - temporaryRegion.selectedBlob.center_x) < 1 &&
                        Math.abs(blob.center_y - temporaryRegion.selectedBlob.center_y) < 1;

                    if (isSelected) {
                        // Selected blob: green, filled
                        ctx.strokeStyle = `rgba(0, 255, 0, ${temporaryRegion.opacity})`;
                        ctx.fillStyle = `rgba(0, 255, 0, ${temporaryRegion.opacity * 0.3})`;
                        ctx.lineWidth = 3;
                    } else {
                        // Other blobs: cyan, unfilled
                        ctx.strokeStyle = `rgba(0, 255, 255, ${temporaryRegion.opacity})`;
                        ctx.fillStyle = 'transparent';
                        ctx.lineWidth = 1.5;
                    }

                    ctx.beginPath();
                    ctx.arc(blob.center_x, blob.center_y, blob.radius_px, 0, Math.PI * 2);
                    if (isSelected) {
                        ctx.fill();
                    }
                    ctx.stroke();
                });
            }

            ctx.restore();
        }
    }

    // Draw a multi-selected tubercle (with fill and thicker stroke)
    function drawMultiSelectedTubercle(tub, colors) {
        const x = tub.centroid_x;
        const y = tub.centroid_y;
        const radius = tub.radius_px;

        // Determine if drawing ellipse or circle
        const useEllipse = toggleState.ellipses && tub.major_axis_px && tub.minor_axis_px;
        const semiMajor = useEllipse ? tub.major_axis_px / 2 : radius;
        const semiMinor = useEllipse ? tub.minor_axis_px / 2 : radius;
        const rotation = useEllipse ? (tub.orientation || 0) : 0;

        // Fill
        ctx.beginPath();
        if (useEllipse) {
            ctx.ellipse(x, y, semiMajor, semiMinor, rotation, 0, 2 * Math.PI);
        } else {
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
        }
        ctx.fillStyle = 'rgba(255, 0, 255, 0.3)';
        ctx.fill();

        // Stroke
        ctx.beginPath();
        if (useEllipse) {
            ctx.ellipse(x, y, semiMajor, semiMinor, rotation, 0, 2 * Math.PI);
        } else {
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
        }
        ctx.strokeStyle = colors.multiSelectedTubercle;
        ctx.lineWidth = 3;
        ctx.stroke();
    }

    // Draw a multi-selected edge (with thicker stroke)
    function drawMultiSelectedEdge(edge, colors) {
        ctx.beginPath();
        ctx.moveTo(edge.x1, edge.y1);
        ctx.lineTo(edge.x2, edge.y2);
        ctx.strokeStyle = colors.multiSelectedEdge;
        ctx.lineWidth = 3;
        ctx.stroke();
    }

    // Draw area selection rectangle
    function drawAreaSelectionRect(start, end, colors) {
        const rect = normalizeRect(start, end);

        ctx.save();
        ctx.strokeStyle = colors.areaSelectStroke;
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        ctx.fillStyle = colors.areaSelectFill;

        ctx.fillRect(rect.x, rect.y, rect.width, rect.height);
        ctx.strokeRect(rect.x, rect.y, rect.width, rect.height);

        ctx.restore();
    }

    // Normalize rectangle coordinates (handle negative width/height)
    function normalizeRect(p1, p2) {
        return {
            x: Math.min(p1.x, p2.x),
            y: Math.min(p1.y, p2.y),
            width: Math.abs(p2.x - p1.x),
            height: Math.abs(p2.y - p1.y)
        };
    }

    // Check if a point is inside a rectangle
    function isPointInRect(px, py, rect) {
        return px >= rect.x && px <= rect.x + rect.width &&
               py >= rect.y && py <= rect.y + rect.height;
    }

    // Draw debug shapes (rectangles, markers)
    function drawDebugShapes(colors) {
        const debugColors = {
            'magenta': '#ff00ff',
            'red': '#ff0000',
            'green': '#00ff00',
            'blue': '#0000ff',
            'yellow': '#ffff00',
            'cyan': '#00ffff',
            'white': '#ffffff',
            'orange': '#ffa500',
        };

        debugShapes.forEach(shape => {
            if (shape.type === 'rectangle') {
                const color = debugColors[shape.color] || '#ff00ff';
                const x = shape.x * scale;
                const y = shape.y * scale;
                const width = shape.width * scale;
                const height = shape.height * scale;

                // Draw rectangle outline
                ctx.strokeStyle = color;
                ctx.lineWidth = 3;
                ctx.setLineDash([10, 5]);
                ctx.strokeRect(x, y, width, height);
                ctx.setLineDash([]);

                // Draw corner markers
                const markerSize = 15;
                ctx.lineWidth = 3;
                // Top-left
                ctx.beginPath();
                ctx.moveTo(x, y);
                ctx.lineTo(x + markerSize, y);
                ctx.moveTo(x, y);
                ctx.lineTo(x, y + markerSize);
                ctx.stroke();
                // Top-right
                ctx.beginPath();
                ctx.moveTo(x + width, y);
                ctx.lineTo(x + width - markerSize, y);
                ctx.moveTo(x + width, y);
                ctx.lineTo(x + width, y + markerSize);
                ctx.stroke();
                // Bottom-left
                ctx.beginPath();
                ctx.moveTo(x, y + height);
                ctx.lineTo(x + markerSize, y + height);
                ctx.moveTo(x, y + height);
                ctx.lineTo(x, y + height - markerSize);
                ctx.stroke();
                // Bottom-right
                ctx.beginPath();
                ctx.moveTo(x + width, y + height);
                ctx.lineTo(x + width - markerSize, y + height);
                ctx.moveTo(x + width, y + height);
                ctx.lineTo(x + width, y + height - markerSize);
                ctx.stroke();

                // Draw label if present
                if (shape.label) {
                    ctx.font = '14px Arial, sans-serif';
                    ctx.fillStyle = color;
                    ctx.fillText(shape.label, x + 5, y + 18);
                }
            }
        });
    }

    // Draw calibration scale bar
    function drawCalibrationScale() {
        if (!canvas || !ctx) return;

        // Get calibration
        const calibration = window.calibration && window.calibration.getCurrentCalibration();
        const umPerPx = calibration ? calibration.um_per_px : 0.14; // Default to estimate

        // Determine a nice scale bar length
        // Aim for approximately 10% of image width
        const targetWidthPx = canvas.width * 0.1;
        const targetWidthUm = targetWidthPx * umPerPx;

        // Round to a nice number
        const niceValues = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000];
        let scaleUm = 10;
        for (let i = 0; i < niceValues.length; i++) {
            if (niceValues[i] >= targetWidthUm) {
                scaleUm = niceValues[i];
                break;
            }
        }

        const scalePx = scaleUm / umPerPx;
        const position = (window.settings && window.settings.get('scalePosition')) || 'bottom-left';
        const padding = 20;
        const barHeight = 6;
        const labelOffset = 16;

        // Calculate position
        let x, y;
        switch (position) {
            case 'top-left':
                x = padding;
                y = padding;
                break;
            case 'top-center':
                x = (canvas.width - scalePx) / 2;
                y = padding;
                break;
            case 'top-right':
                x = canvas.width - scalePx - padding;
                y = padding;
                break;
            case 'middle-left':
                x = padding;
                y = canvas.height / 2;
                break;
            case 'middle-right':
                x = canvas.width - scalePx - padding;
                y = canvas.height / 2;
                break;
            case 'bottom-left':
                x = padding;
                y = canvas.height - padding - barHeight;
                break;
            case 'bottom-center':
                x = (canvas.width - scalePx) / 2;
                y = canvas.height - padding - barHeight;
                break;
            case 'bottom-right':
                x = canvas.width - scalePx - padding;
                y = canvas.height - padding - barHeight;
                break;
            default:
                x = padding;
                y = canvas.height - padding - barHeight;
        }

        // Draw scale bar background for contrast
        ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
        ctx.fillRect(x - 4, y - labelOffset - 4, scalePx + 8, barHeight + labelOffset + 8);

        // Draw scale bar
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(x, y, scalePx, barHeight);

        // Draw end caps
        ctx.fillRect(x, y - 4, 2, barHeight + 8);
        ctx.fillRect(x + scalePx - 2, y - 4, 2, barHeight + 8);

        // Draw label
        const label = scaleUm >= 1000 ? (scaleUm / 1000) + ' mm' : scaleUm + ' µm';
        ctx.font = 'bold 12px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'bottom';
        ctx.fillStyle = '#ffffff';
        ctx.fillText(label, x + scalePx / 2, y - 4);
    }

    // Draw coordinate grid overlay
    function drawCoordinateGrid() {
        if (!canvas || !ctx) return;

        // Get calibration
        const calibration = window.calibration && window.calibration.getCurrentCalibration();
        const umPerPx = calibration ? calibration.um_per_px : null;
        const hasCalibration = umPerPx !== null;

        // Calculate image dimensions
        const imageWidth = canvas.width;
        const imageHeight = canvas.height;

        // Determine coordinate system (µm if calibrated, px otherwise)
        const widthUnits = hasCalibration ? imageWidth * umPerPx : imageWidth;
        const heightUnits = hasCalibration ? imageHeight * umPerPx : imageHeight;
        const unitLabel = hasCalibration ? 'µm' : 'px';

        // Choose nice grid spacing
        const niceValues = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
        const targetLines = 6; // Aim for ~6 lines per axis
        const targetSpacing = Math.max(widthUnits, heightUnits) / targetLines;

        let gridSpacing = niceValues[niceValues.length - 1];
        for (const val of niceValues) {
            if (val >= targetSpacing) {
                gridSpacing = val;
                break;
            }
        }

        // Convert spacing to pixels
        const spacingPx = hasCalibration ? gridSpacing / umPerPx : gridSpacing;

        // Draw settings - get color and opacity from settings
        const baseColor = (window.settings && window.settings.get('gridColor')) || '#ff88ff';
        const gridOpacity = (window.settings && window.settings.get('gridOpacity')) || 0.35;
        // Parse hex color to RGB for transparent version
        const r = parseInt(baseColor.slice(1, 3), 16);
        const g = parseInt(baseColor.slice(3, 5), 16);
        const b = parseInt(baseColor.slice(5, 7), 16);
        const gridLineColor = `rgba(${r}, ${g}, ${b}, ${gridOpacity})`;
        const labelColor = baseColor;
        const labelShadow = '#000000';
        const fontSize = 11;
        const labelPadding = 4;

        ctx.save();

        // Draw vertical grid lines and X-axis labels
        ctx.strokeStyle = gridLineColor;
        ctx.lineWidth = 1;
        ctx.font = `${fontSize}px sans-serif`;

        for (let xPx = 0; xPx <= imageWidth; xPx += spacingPx) {
            const coordValue = hasCalibration ? xPx * umPerPx : xPx;

            // Draw vertical line
            ctx.beginPath();
            ctx.moveTo(xPx, 0);
            ctx.lineTo(xPx, imageHeight);
            ctx.stroke();

            // Draw X label at top
            if (xPx > 0 && xPx < imageWidth - 30) {
                const label = formatGridLabel(coordValue);
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                // Draw with shadow for visibility
                ctx.fillStyle = labelShadow;
                ctx.fillText(label, xPx + 1, labelPadding + 1);
                ctx.fillStyle = labelColor;
                ctx.fillText(label, xPx, labelPadding);
            }
        }

        // Draw horizontal grid lines and Y-axis labels
        for (let yPx = 0; yPx <= imageHeight; yPx += spacingPx) {
            const coordValue = hasCalibration ? yPx * umPerPx : yPx;

            // Draw horizontal line
            ctx.beginPath();
            ctx.moveTo(0, yPx);
            ctx.lineTo(imageWidth, yPx);
            ctx.stroke();

            // Draw Y label at left
            if (yPx > 15 && yPx < imageHeight - 10) {
                const label = formatGridLabel(coordValue);
                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = labelShadow;
                ctx.fillText(label, labelPadding + 1, yPx + 1);
                ctx.fillStyle = labelColor;
                ctx.fillText(label, labelPadding, yPx);
            }
        }

        // Draw origin label with unit indicator
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';
        const originLabel = `0 ${unitLabel}`;
        // Background box for origin label
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        const metrics = ctx.measureText(originLabel);
        ctx.fillRect(labelPadding - 2, labelPadding - 2, metrics.width + 4, fontSize + 4);
        // Label text
        ctx.fillStyle = labelShadow;
        ctx.fillText(originLabel, labelPadding + 1, labelPadding + 1);
        ctx.fillStyle = labelColor;
        ctx.fillText(originLabel, labelPadding, labelPadding);

        ctx.restore();
    }

    // Format coordinate grid label (remove unnecessary decimals)
    function formatGridLabel(value) {
        if (value === 0) return '0';
        if (value >= 100) return Math.round(value).toString();
        if (value >= 10) return value.toFixed(0);
        if (value >= 1) return value.toFixed(1);
        return value.toFixed(2);
    }

    // Draw a single tubercle (as circle or ellipse)
    function drawTubercle(tub, isSelected, colors) {
        const x = tub.centroid_x;
        const y = tub.centroid_y;
        const radius = tub.radius_px;

        ctx.beginPath();

        // Draw ellipse if toggle is on and ellipse data is available
        if (toggleState.ellipses && tub.major_axis_px && tub.minor_axis_px) {
            // major_axis_px and minor_axis_px are full axis lengths, so divide by 2 for radii
            const semiMajor = tub.major_axis_px / 2;
            const semiMinor = tub.minor_axis_px / 2;
            const rotation = tub.orientation || 0;  // radians
            ctx.ellipse(x, y, semiMajor, semiMinor, rotation, 0, 2 * Math.PI);
        } else {
            // Draw circle (default)
            ctx.arc(x, y, radius, 0, 2 * Math.PI);
        }

        ctx.strokeStyle = getTubercleColor(tub, colors, isSelected);
        const isDebugSeed = tub.source === 'debug_seed';
        ctx.lineWidth = isSelected ? 3 : (isDebugSeed ? 4 : 2);
        ctx.stroke();

        // Draw cross-hairs for debug seeds (additional visual marker)
        if (isDebugSeed) {
            const crossSize = radius * 0.5;
            ctx.beginPath();
            ctx.moveTo(x - crossSize, y);
            ctx.lineTo(x + crossSize, y);
            ctx.moveTo(x, y - crossSize);
            ctx.lineTo(x, y + crossSize);
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    }

    // Draw tubercle ID text
    function drawTubercleId(tub, fontSize, colors) {
        const x = tub.centroid_x;
        const y = tub.centroid_y;

        ctx.font = `bold ${fontSize}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Draw text with outline for visibility
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 3;
        ctx.strokeText(tub.id, x, y);

        ctx.fillStyle = getTubercleColor(tub, colors, false);
        ctx.fillText(tub.id, x, y);
    }

    // Draw edge (ITC) ID text at midpoint
    function drawEdgeId(edge, idx, fontSize, colors) {
        // Calculate midpoint of the edge
        const x = (edge.x1 + edge.x2) / 2;
        const y = (edge.y1 + edge.y2) / 2;

        ctx.font = `bold ${fontSize}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        // Draw text with outline for visibility
        ctx.strokeStyle = '#000000';
        ctx.lineWidth = 3;
        ctx.strokeText(idx, x, y);

        ctx.fillStyle = colors.edge;
        ctx.fillText(idx, x, y);
    }

    // Draw a single edge
    function drawEdge(edge, isSelected, isHighlighted, colors) {
        // Determine endpoint mode
        const endpointMode = (window.settings && window.settings.get('connectionEndpoint')) || 'center';

        let x1 = edge.x1;
        let y1 = edge.y1;
        let x2 = edge.x2;
        let y2 = edge.y2;

        // If drawing to edge, adjust endpoints
        if (endpointMode === 'edge') {
            // Find the tubercles
            const tub1 = tubercles.find(t => t.id === edge.id1);
            const tub2 = tubercles.find(t => t.id === edge.id2);

            if (tub1 && tub2) {
                const dx = x2 - x1;
                const dy = y2 - y1;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist > 0) {
                    // Normalize direction
                    const nx = dx / dist;
                    const ny = dy / dist;

                    // Offset from center by radius
                    x1 = x1 + nx * tub1.radius_px;
                    y1 = y1 + ny * tub1.radius_px;
                    x2 = x2 - nx * tub2.radius_px;
                    y2 = y2 - ny * tub2.radius_px;
                }
            }
        }

        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);

        // Determine color: selected > highlighted > normal
        if (isSelected) {
            ctx.strokeStyle = colors.selectedEdge;
            ctx.lineWidth = 3;
        } else if (isHighlighted) {
            ctx.strokeStyle = colors.highlightedEdge;
            ctx.lineWidth = 4;
        } else {
            ctx.strokeStyle = colors.edge;
            ctx.lineWidth = 2;
        }
        ctx.stroke();
    }

    // Handle click for selection
    function handleClick(e) {
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        // Account for zoom/scale
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        // Check if editor is in an edit mode that needs to handle clicks
        const editorMode = window.editor?.getMode();
        if (editorMode && editorMode !== 'none') {
            // Pass click to editor for handling
            window.editor.handleCanvasClick(x, y);
            return;
        }

        // Check for both tubercle and edge clicks, select whichever is closer
        let closestTub = null;
        let closestTubDist = Infinity;

        if (toggleState.tubes) {
            tubercles.forEach(tub => {
                const dx = x - tub.centroid_x;
                const dy = y - tub.centroid_y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                // Click within radius * 1.5 for easier selection
                if (dist < tub.radius_px * 1.5 && dist < closestTubDist) {
                    closestTubDist = dist;
                    closestTub = tub;
                }
            });
        }

        // Check for edge click (within threshold of line) - only if links are visible
        const clickThreshold = 10;
        let closestEdge = null;
        let closestEdgeDist = Infinity;

        if (toggleState.links) {
            edges.forEach((edge, idx) => {
                const dist = pointToLineDistance(x, y, edge.x1, edge.y1, edge.x2, edge.y2);
                if (dist < clickThreshold && dist < closestEdgeDist) {
                    closestEdgeDist = dist;
                    closestEdge = idx;
                }
            });
        }

        // Select whichever is more appropriate
        if (closestTub && closestEdge !== null) {
            // Both are valid - if click is inside the tubercle radius, prefer tubercle
            // Only prefer edge if click is outside the tubercle but within the extended hit area
            if (closestTubDist <= closestTub.radius_px) {
                // Click is inside tubercle - select tubercle
                selectTubercle(closestTub.id);
            } else if (closestEdgeDist < closestTubDist * 0.5) {
                // Click is outside tubercle but much closer to edge - select edge
                selectEdge(closestEdge);
            } else {
                // Default to tubercle
                selectTubercle(closestTub.id);
            }
            return;
        }

        if (closestTub) {
            selectTubercle(closestTub.id);
            return;
        }

        if (closestEdge !== null) {
            selectEdge(closestEdge);
            return;
        }

        // Click on empty space - deselect
        deselect();
    }

    // Distance from point to line segment
    function pointToLineDistance(px, py, x1, y1, x2, y2) {
        const A = px - x1;
        const B = py - y1;
        const C = x2 - x1;
        const D = y2 - y1;

        const dot = A * C + B * D;
        const lenSq = C * C + D * D;
        let param = -1;

        if (lenSq !== 0) param = dot / lenSq;

        let xx, yy;

        if (param < 0) {
            xx = x1;
            yy = y1;
        } else if (param > 1) {
            xx = x2;
            yy = y2;
        } else {
            xx = x1 + param * C;
            yy = y1 + param * D;
        }

        const dx = px - xx;
        const dy = py - yy;
        return Math.sqrt(dx * dx + dy * dy);
    }

    // Select a tubercle
    function selectTubercle(id) {
        selectedTubId = id;
        selectedEdgeIdx = null;
        render();

        // Notify data table
        if (window.data && window.data.highlightTubercleRow) {
            window.data.highlightTubercleRow(id);
        }

        // Dispatch event
        document.dispatchEvent(new CustomEvent('tubercleSelected', { detail: { id } }));
    }

    // Select an edge
    function selectEdge(idx) {
        selectedEdgeIdx = idx;
        selectedTubId = null;
        render();

        // Notify data table
        if (window.data && window.data.highlightEdgeRow) {
            window.data.highlightEdgeRow(idx);
        }

        // Dispatch event
        document.dispatchEvent(new CustomEvent('edgeSelected', { detail: { idx } }));
    }

    // Deselect all
    function deselect() {
        selectedTubId = null;
        selectedEdgeIdx = null;
        render();

        // Clear table highlights
        if (window.data && window.data.clearHighlights) {
            window.data.clearHighlights();
        }

        // Dispatch event
        document.dispatchEvent(new CustomEvent('overlayDeselected'));
    }

    // Get selected tubercle
    function getSelectedTubercle() {
        if (selectedTubId === null) return null;
        return tubercles.find(t => t.id === selectedTubId);
    }

    // Get selected edge
    function getSelectedEdge() {
        if (selectedEdgeIdx === null) return null;
        return edges[selectedEdgeIdx];
    }

    // Highlight a tubercle (called from data table)
    function highlightTubercle(id) {
        selectedTubId = id;
        selectedEdgeIdx = null;
        render();
    }

    // Highlight an edge (called from data table)
    function highlightEdge(idx) {
        selectedEdgeIdx = idx;
        selectedTubId = null;
        render();
    }

    // Set highlighted edge for chain mode navigation preview
    function setHighlightedEdge(edge) {
        highlightedEdge = edge;
        render();
    }

    // Get current data (for editor)
    function getTubercles() {
        return tubercles;
    }

    function getEdges() {
        return edges;
    }

    // ========================================
    // Multi-selection functions
    // ========================================

    // Select multiple tubercles by ID
    function selectMultipleTubercles(ids) {
        selectedTubIds = new Set(ids);
        // Clear single selection
        selectedTubId = null;
        render();
        dispatchMultiSelectionEvent();
    }

    // Select multiple edges by index
    function selectMultipleEdges(idxs) {
        selectedEdgeIdxs = new Set(idxs);
        // Clear single selection
        selectedEdgeIdx = null;
        render();
        dispatchMultiSelectionEvent();
    }

    // Add to existing multi-selection
    function addToMultiSelection(tubIds, edgeIdxs) {
        if (tubIds) {
            tubIds.forEach(id => selectedTubIds.add(id));
        }
        if (edgeIdxs) {
            edgeIdxs.forEach(idx => selectedEdgeIdxs.add(idx));
        }
        render();
        dispatchMultiSelectionEvent();
    }

    // Clear multi-selection
    function clearMultiSelection() {
        selectedTubIds.clear();
        selectedEdgeIdxs.clear();
        render();
        dispatchMultiSelectionEvent();
    }

    // Get selected tubercle objects (not just IDs)
    function getMultiSelectedTubercles() {
        return tubercles.filter(t => selectedTubIds.has(t.id));
    }

    // Get selected edge objects (not just indices)
    function getMultiSelectedEdges() {
        return [...selectedEdgeIdxs].map(idx => edges[idx]).filter(e => e);
    }

    // Get multi-selection counts
    function getMultiSelectionCounts() {
        return {
            tubercles: selectedTubIds.size,
            edges: selectedEdgeIdxs.size
        };
    }

    // Check if there's a multi-selection
    function hasMultiSelection() {
        return selectedTubIds.size > 0 || selectedEdgeIdxs.size > 0;
    }

    // Dispatch multi-selection change event
    function dispatchMultiSelectionEvent() {
        document.dispatchEvent(new CustomEvent('multiSelectionChanged', {
            detail: {
                tubercleCount: selectedTubIds.size,
                edgeCount: selectedEdgeIdxs.size,
                tubercleIds: Array.from(selectedTubIds),
                edgeIndices: Array.from(selectedEdgeIdxs)
            }
        }));
    }

    // ========================================
    // Area selection functions
    // ========================================

    // Start area selection (called on mousedown)
    function startAreaSelect(x, y) {
        isAreaSelecting = true;
        areaSelectStart = { x, y };
        areaSelectEnd = { x, y };
        render();
    }

    // Update area selection (called on mousemove)
    function updateAreaSelect(x, y) {
        if (!isAreaSelecting) return;
        areaSelectEnd = { x, y };
        render();
    }

    // Finish area selection and return selected items
    function finishAreaSelect() {
        if (!isAreaSelecting || !areaSelectStart || !areaSelectEnd) {
            return { tubIds: [], edgeIdxs: [] };
        }

        const rect = normalizeRect(areaSelectStart, areaSelectEnd);

        // Find tubercles with centers inside rectangle
        const tubIds = tubercles
            .filter(t => isPointInRect(t.centroid_x, t.centroid_y, rect))
            .map(t => t.id);

        // Find edges with BOTH endpoints inside rectangle
        const edgeIdxs = edges
            .map((e, idx) => ({ e, idx }))
            .filter(({ e }) =>
                isPointInRect(e.x1, e.y1, rect) &&
                isPointInRect(e.x2, e.y2, rect))
            .map(({ idx }) => idx);

        // Clear area selection state
        isAreaSelecting = false;
        areaSelectStart = null;
        areaSelectEnd = null;
        render();

        return { tubIds, edgeIdxs };
    }

    // Cancel area selection
    function cancelAreaSelect() {
        isAreaSelecting = false;
        areaSelectStart = null;
        areaSelectEnd = null;
        render();
    }

    // Check if currently in area selection mode
    function isInAreaSelectMode() {
        return isAreaSelecting;
    }

    // Get canvas for mouse event registration
    function getCanvas() {
        return canvas;
    }

    // Convert client coordinates to image coordinates
    function clientToImageCoords(clientX, clientY) {
        if (!canvas) return { x: 0, y: 0 };
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        return {
            x: (clientX - rect.left) * scaleX,
            y: (clientY - rect.top) * scaleY
        };
    }

    // Temporary region display for auto-size feedback
    let temporaryRegion = null;
    let temporaryRegionTimeout = null;

    /**
     * Show a temporary rectangle on the overlay (fades out after duration)
     * @param {number} x - X coordinate of top-left corner
     * @param {number} y - Y coordinate of top-left corner
     * @param {number} width - Width of rectangle
     * @param {number} height - Height of rectangle
     * @param {number} duration - Duration to show in milliseconds
     * @param {Array} allBlobs - All detected blobs [{center_x, center_y, radius_px}, ...]
     * @param {Object|null} selectedBlob - The blob that was selected, or null
     */
    function showTemporaryRegion(x, y, width, height, duration = 3000, allBlobs = [], selectedBlob = null) {
        // Clear any existing timeout
        if (temporaryRegionTimeout) {
            clearTimeout(temporaryRegionTimeout);
        }

        temporaryRegion = { x, y, width, height, opacity: 1.0, allBlobs, selectedBlob };
        render();

        // Fade out over the last 500ms
        const fadeStart = duration - 500;
        const fadeSteps = 10;
        const fadeStepDuration = 500 / fadeSteps;

        // Start fade after initial display
        setTimeout(() => {
            let step = 0;
            const fadeInterval = setInterval(() => {
                step++;
                if (temporaryRegion) {
                    temporaryRegion.opacity = 1.0 - (step / fadeSteps);
                    render();
                }
                if (step >= fadeSteps) {
                    clearInterval(fadeInterval);
                    temporaryRegion = null;
                    render();
                }
            }, fadeStepDuration);
        }, fadeStart);

        // Clear after full duration (backup)
        temporaryRegionTimeout = setTimeout(() => {
            temporaryRegion = null;
            render();
        }, duration + 100);
    }

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    return {
        init,
        resize,
        setScale,
        setData,
        setDebugShapes,
        clear,
        render,
        selectTubercle,
        selectEdge,
        deselect,
        highlightTubercle,
        highlightEdge,
        setHighlightedEdge,
        getSelectedTubercle,
        getSelectedEdge,
        getTubercles,
        getEdges,
        initToggleStates,
        setColorMode,
        // Multi-selection
        selectMultipleTubercles,
        selectMultipleEdges,
        addToMultiSelection,
        clearMultiSelection,
        getMultiSelectedTubercles,
        getMultiSelectedEdges,
        getMultiSelectionCounts,
        hasMultiSelection,
        // Area selection
        startAreaSelect,
        updateAreaSelect,
        finishAreaSelect,
        cancelAreaSelect,
        isInAreaSelectMode,
        getCanvas,
        clientToImageCoords,
        showTemporaryRegion,
    };
})();
