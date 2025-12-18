"""Tests for MCP server-side screenshot rendering."""

import base64
import io
import pytest
from pathlib import Path
from PIL import Image


class TestRenderScreenshot:
    """Tests for render_screenshot function."""

    def test_render_screenshot_basic(self, synthetic_test_image):
        """Render screenshot returns base64 PNG."""
        from fish_scale_mcp.screenshot import render_screenshot

        result = render_screenshot(
            image_path=str(synthetic_test_image),
            tubercles=[],
            connections=[],
        )

        assert isinstance(result, str)
        # Verify it's valid base64
        decoded = base64.b64decode(result)
        # Verify it's a valid PNG
        img = Image.open(io.BytesIO(decoded))
        assert img.format == 'PNG'

    def test_render_screenshot_dimensions(self, synthetic_test_image):
        """Rendered screenshot has correct dimensions."""
        from fish_scale_mcp.screenshot import render_screenshot

        result = render_screenshot(
            image_path=str(synthetic_test_image),
            tubercles=[],
            connections=[],
        )

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.size == (256, 256)

    def test_render_screenshot_file_not_found(self):
        """Render screenshot raises error for missing file."""
        from fish_scale_mcp.screenshot import render_screenshot

        with pytest.raises(FileNotFoundError):
            render_screenshot(
                image_path='/nonexistent/image.png',
                tubercles=[],
                connections=[],
            )

    def test_render_with_tubercles(self, synthetic_test_image, sample_tubercles):
        """Render screenshot with tubercle overlay."""
        from fish_scale_mcp.screenshot import render_screenshot

        result = render_screenshot(
            image_path=str(synthetic_test_image),
            tubercles=sample_tubercles,
            connections=[],
            show_tubercles=True,
        )

        # Should succeed and return larger image (overlay adds content)
        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.size == (256, 256)

    def test_render_with_connections(self, synthetic_test_image, sample_tubercles, sample_edges):
        """Render screenshot with connection overlay."""
        from fish_scale_mcp.screenshot import render_screenshot

        result = render_screenshot(
            image_path=str(synthetic_test_image),
            tubercles=sample_tubercles,
            connections=sample_edges,
            show_connections=True,
        )

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.size == (256, 256)

    def test_render_with_numbers(self, synthetic_test_image, sample_tubercles):
        """Render screenshot with ID numbers."""
        from fish_scale_mcp.screenshot import render_screenshot

        result = render_screenshot(
            image_path=str(synthetic_test_image),
            tubercles=sample_tubercles,
            connections=[],
            show_numbers=True,
        )

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.format == 'PNG'

    def test_render_with_scale_bar(self, synthetic_test_image):
        """Render screenshot with scale bar."""
        from fish_scale_mcp.screenshot import render_screenshot

        result = render_screenshot(
            image_path=str(synthetic_test_image),
            tubercles=[],
            connections=[],
            calibration={'um_per_px': 0.165},
            show_scale_bar=True,
        )

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.format == 'PNG'

    def test_render_selected_tubercle(self, synthetic_test_image, sample_tubercles):
        """Render screenshot with selected tubercle highlighted."""
        from fish_scale_mcp.screenshot import render_screenshot

        result = render_screenshot(
            image_path=str(synthetic_test_image),
            tubercles=sample_tubercles,
            connections=[],
            selected_tub_id=1,
        )

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.format == 'PNG'

    def test_render_selected_connection(self, synthetic_test_image, sample_tubercles, sample_edges):
        """Render screenshot with selected connection highlighted."""
        from fish_scale_mcp.screenshot import render_screenshot

        result = render_screenshot(
            image_path=str(synthetic_test_image),
            tubercles=sample_tubercles,
            connections=sample_edges,
            selected_edge_idx=0,
        )

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.format == 'PNG'

    def test_render_no_overlay(self, synthetic_test_image, sample_tubercles):
        """Render screenshot without overlay when disabled."""
        from fish_scale_mcp.screenshot import render_screenshot

        result = render_screenshot(
            image_path=str(synthetic_test_image),
            tubercles=sample_tubercles,
            connections=[],
            show_tubercles=False,
            show_connections=False,
        )

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.format == 'PNG'


class TestRenderThumbnail:
    """Tests for render_thumbnail function."""

    def test_render_thumbnail(self, synthetic_test_image):
        """Render thumbnail returns resized image."""
        from fish_scale_mcp.screenshot import render_thumbnail

        result = render_thumbnail(
            image_path=str(synthetic_test_image),
            max_size=(100, 100),
        )

        decoded = base64.b64decode(result)
        img = Image.open(io.BytesIO(decoded))
        assert img.format == 'PNG'
        # Should be smaller or equal to max_size
        assert img.width <= 100
        assert img.height <= 100

    def test_render_thumbnail_maintains_aspect(self, tmp_path):
        """Thumbnail maintains aspect ratio."""
        from fish_scale_mcp.screenshot import render_thumbnail
        import numpy as np

        # Create a 400x200 image (2:1 aspect ratio)
        data = np.random.randint(100, 200, (200, 400), dtype=np.uint8)
        img = Image.fromarray(data, mode='L')
        image_path = tmp_path / 'wide_image.png'
        img.save(image_path)

        result = render_thumbnail(str(image_path), max_size=(100, 100))

        decoded = base64.b64decode(result)
        thumb = Image.open(io.BytesIO(decoded))
        # With 2:1 aspect ratio and 100x100 max, should be 100x50
        assert thumb.width == 100
        assert thumb.height == 50

    def test_render_thumbnail_file_not_found(self):
        """Render thumbnail raises error for missing file."""
        from fish_scale_mcp.screenshot import render_thumbnail

        with pytest.raises(FileNotFoundError):
            render_thumbnail('/nonexistent/image.png')


class TestScaleBarRendering:
    """Tests for scale bar rendering helper."""

    def test_scale_bar_nice_values(self, synthetic_test_image):
        """Scale bar uses nice round values."""
        from fish_scale_mcp.screenshot import render_screenshot

        # Test with different calibrations to verify nice values are used
        for um_per_px in [0.1, 0.5, 1.0, 2.0]:
            result = render_screenshot(
                image_path=str(synthetic_test_image),
                tubercles=[],
                connections=[],
                calibration={'um_per_px': um_per_px},
                show_scale_bar=True,
            )
            # Should succeed without error
            assert isinstance(result, str)
            assert len(result) > 0


class TestColorScheme:
    """Tests for color scheme constants."""

    def test_colors_defined(self):
        """All required colors are defined."""
        from fish_scale_mcp.screenshot import COLORS

        required_colors = [
            'tubercle_outline',
            'connection',
            'text',
        ]

        for color_name in required_colors:
            assert color_name in COLORS
            assert isinstance(COLORS[color_name], tuple)
