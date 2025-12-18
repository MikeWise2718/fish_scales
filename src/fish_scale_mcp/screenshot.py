"""Server-side screenshot rendering for MCP.

Renders fish scale images with tubercle/connection overlays without browser dependency.
"""

import base64
import io
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


# Overlay colors (RGB tuples)
COLORS = {
    'tubercle_outline': (0, 255, 255),      # Cyan - extracted tubercles
    'tubercle_manual': (0, 255, 0),         # Green - manually added tubercles
    'tubercle_fill': (0, 255, 255, 50),     # Cyan with alpha
    'tubercle_selected': (255, 0, 255),     # Magenta for selection
    'connection': (255, 255, 0),            # Yellow
    'connection_selected': (255, 0, 255),   # Magenta
    'text': (255, 255, 255),                # White
    'text_bg': (0, 0, 0, 180),              # Black with alpha
}


def render_screenshot(
    image_path: str,
    tubercles: list,
    connections: list,
    calibration: Optional[dict] = None,
    show_tubercles: bool = True,
    show_connections: bool = True,
    show_numbers: bool = False,
    show_scale_bar: bool = False,
    selected_tub_id: Optional[int] = None,
    selected_edge_idx: Optional[int] = None,
    debug_shapes: Optional[list] = None,
) -> str:
    """Render image with overlay and return as base64 PNG.

    Args:
        image_path: Path to the image file
        tubercles: List of tubercle dicts with id, centroid_x, centroid_y, radius_px
        connections: List of connection dicts with id1, id2, x1, y1, x2, y2
        calibration: Optional calibration dict with um_per_px
        show_tubercles: Whether to draw tubercle circles
        show_connections: Whether to draw connection lines
        show_numbers: Whether to draw tubercle ID numbers
        show_scale_bar: Whether to draw a scale bar
        selected_tub_id: ID of selected tubercle (highlighted yellow)
        selected_edge_idx: Index of selected edge (highlighted yellow)
        debug_shapes: Optional list of debug shapes (rectangles, etc.)

    Returns:
        Base64-encoded PNG image string
    """
    # Load image
    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with Image.open(img_path) as img:
        # Convert to RGBA for overlay
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # Create overlay layer
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Draw connections first (under tubercles)
        if show_connections and connections:
            for idx, conn in enumerate(connections):
                x1, y1 = conn.get('x1', 0), conn.get('y1', 0)
                x2, y2 = conn.get('x2', 0), conn.get('y2', 0)

                color = COLORS['connection_selected'] if idx == selected_edge_idx else COLORS['connection']
                width = 3 if idx == selected_edge_idx else 2

                draw.line([(x1, y1), (x2, y2)], fill=color, width=width)

        # Draw tubercles
        if show_tubercles and tubercles:
            for tub in tubercles:
                tub_id = tub.get('id', 0)
                cx = tub.get('centroid_x', 0)
                cy = tub.get('centroid_y', 0)
                radius = tub.get('radius_px', 10)
                source = tub.get('source', 'extracted')

                # Determine colors based on selection and source
                is_selected = tub_id == selected_tub_id
                if is_selected:
                    outline_color = COLORS['tubercle_selected']
                elif source == 'manual':
                    outline_color = COLORS['tubercle_manual']
                else:
                    outline_color = COLORS['tubercle_outline']
                width = 3 if is_selected else 2

                # Draw circle outline
                bbox = [cx - radius, cy - radius, cx + radius, cy + radius]
                draw.ellipse(bbox, outline=outline_color, width=width)

                # Draw ID number if enabled
                if show_numbers:
                    text = str(tub_id)
                    # Try to get font, fall back to default
                    try:
                        font = ImageFont.truetype("arial.ttf", 12)
                    except (IOError, OSError):
                        font = ImageFont.load_default()

                    # Get text size
                    text_bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = text_bbox[2] - text_bbox[0]
                    text_height = text_bbox[3] - text_bbox[1]

                    # Position text above tubercle
                    text_x = cx - text_width / 2
                    text_y = cy - radius - text_height - 4

                    # Draw background rectangle
                    padding = 2
                    draw.rectangle(
                        [text_x - padding, text_y - padding,
                         text_x + text_width + padding, text_y + text_height + padding],
                        fill=COLORS['text_bg']
                    )

                    # Draw text
                    draw.text((text_x, text_y), text, fill=COLORS['text'], font=font)

        # Draw scale bar if enabled and calibration is available
        if show_scale_bar and calibration:
            um_per_px = calibration.get('um_per_px', 0)
            if um_per_px > 0:
                _draw_scale_bar(draw, img.size, um_per_px)

        # Draw debug shapes (rectangles, markers)
        if debug_shapes:
            _draw_debug_shapes(draw, debug_shapes)

        # Composite overlay onto image
        result = Image.alpha_composite(img, overlay)

        # Convert to RGB for PNG output (no alpha needed in final)
        result = result.convert('RGB')

        # Encode as base64 PNG
        buffer = io.BytesIO()
        result.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return base64.b64encode(buffer.read()).decode('utf-8')


DEBUG_COLORS = {
    'magenta': (255, 0, 255),
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'cyan': (0, 255, 255),
    'white': (255, 255, 255),
    'orange': (255, 165, 0),
}


def _draw_debug_shapes(draw: ImageDraw.Draw, shapes: list):
    """Draw debug shapes (rectangles, markers) on the overlay."""
    for shape in shapes:
        shape_type = shape.get('type', 'rectangle')
        color_name = shape.get('color', 'magenta')
        color = DEBUG_COLORS.get(color_name, (255, 0, 255))

        if shape_type == 'rectangle':
            x = shape.get('x', 0)
            y = shape.get('y', 0)
            width = shape.get('width', 100)
            height = shape.get('height', 100)
            label = shape.get('label', '')

            # Draw rectangle outline (no fill)
            draw.rectangle(
                [x, y, x + width, y + height],
                outline=color,
                width=3
            )

            # Draw corner markers for visibility
            marker_size = 10
            # Top-left
            draw.line([(x, y), (x + marker_size, y)], fill=color, width=3)
            draw.line([(x, y), (x, y + marker_size)], fill=color, width=3)
            # Top-right
            draw.line([(x + width, y), (x + width - marker_size, y)], fill=color, width=3)
            draw.line([(x + width, y), (x + width, y + marker_size)], fill=color, width=3)
            # Bottom-left
            draw.line([(x, y + height), (x + marker_size, y + height)], fill=color, width=3)
            draw.line([(x, y + height), (x, y + height - marker_size)], fill=color, width=3)
            # Bottom-right
            draw.line([(x + width, y + height), (x + width - marker_size, y + height)], fill=color, width=3)
            draw.line([(x + width, y + height), (x + width, y + height - marker_size)], fill=color, width=3)

            # Draw label if provided
            if label:
                try:
                    font = ImageFont.truetype("arial.ttf", 14)
                except (IOError, OSError):
                    font = ImageFont.load_default()

                text_bbox = draw.textbbox((0, 0), label, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]

                # Position label at top-left inside the rectangle
                text_x = x + 5
                text_y = y + 5

                # Draw background
                draw.rectangle(
                    [text_x - 2, text_y - 2, text_x + text_width + 2, text_y + text_height + 2],
                    fill=(0, 0, 0, 200)
                )
                draw.text((text_x, text_y), label, fill=color, font=font)


def _draw_scale_bar(draw: ImageDraw.Draw, img_size: tuple, um_per_px: float):
    """Draw a scale bar in the bottom-right corner."""
    width, height = img_size

    # Calculate scale bar length (aim for ~100 pixels)
    target_px = 100
    target_um = target_px * um_per_px

    # Round to nice number
    nice_values = [1, 2, 5, 10, 20, 50, 100, 200, 500]
    scale_um = min(nice_values, key=lambda x: abs(x - target_um))
    scale_px = int(scale_um / um_per_px)

    # Position in bottom-right
    margin = 20
    bar_height = 8
    x1 = width - margin - scale_px
    x2 = width - margin
    y1 = height - margin - bar_height
    y2 = height - margin

    # Draw bar background
    draw.rectangle([x1 - 2, y1 - 20, x2 + 2, y2 + 2], fill=(0, 0, 0, 180))

    # Draw bar
    draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255), outline=(255, 255, 255))

    # Draw label
    label = f"{scale_um} \u00b5m"
    try:
        font = ImageFont.truetype("arial.ttf", 12)
    except (IOError, OSError):
        font = ImageFont.load_default()

    text_bbox = draw.textbbox((0, 0), label, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_x = x1 + (scale_px - text_width) / 2
    text_y = y1 - 16

    draw.text((text_x, text_y), label, fill=(255, 255, 255), font=font)


def render_thumbnail(
    image_path: str,
    max_size: tuple = (400, 400),
) -> str:
    """Render a thumbnail of the image as base64 PNG.

    Args:
        image_path: Path to the image file
        max_size: Maximum dimensions (width, height)

    Returns:
        Base64-encoded PNG image string
    """
    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with Image.open(img_path) as img:
        # Convert to RGB
        if img.mode not in ('RGB', 'RGBA'):
            img = img.convert('RGB')

        # Create thumbnail
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Encode as base64 PNG
        buffer = io.BytesIO()
        img.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)

        return base64.b64encode(buffer.read()).decode('utf-8')
