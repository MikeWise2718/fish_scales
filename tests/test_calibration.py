"""Tests for calibration module."""

import pytest
from fish_scale_analysis.core.calibration import (
    calibrate_manual,
    estimate_calibration_700x,
    calibrate_from_known_magnification,
)


class TestManualCalibration:
    """Tests for manual calibration."""

    def test_basic_calibration(self):
        """Test basic manual calibration calculation."""
        cal = calibrate_manual(scale_bar_um=10.0, scale_bar_px=100.0)

        assert cal.um_per_pixel == 0.1
        assert cal.scale_bar_length_um == 10.0
        assert cal.scale_bar_length_px == 100.0
        assert cal.method == "manual"

    def test_px_to_um_conversion(self):
        """Test pixel to micrometer conversion."""
        cal = calibrate_manual(scale_bar_um=10.0, scale_bar_px=50.0)

        # 50 pixels = 10 µm, so 1 pixel = 0.2 µm
        assert cal.px_to_um(50) == 10.0
        assert cal.px_to_um(100) == 20.0
        assert cal.px_to_um(25) == 5.0

    def test_um_to_px_conversion(self):
        """Test micrometer to pixel conversion."""
        cal = calibrate_manual(scale_bar_um=10.0, scale_bar_px=50.0)

        assert cal.um_to_px(10.0) == 50.0
        assert cal.um_to_px(20.0) == 100.0
        assert cal.um_to_px(5.0) == 25.0

    def test_invalid_scale_bar_px(self):
        """Test that zero or negative pixel value raises error."""
        with pytest.raises(ValueError):
            calibrate_manual(scale_bar_um=10.0, scale_bar_px=0)

        with pytest.raises(ValueError):
            calibrate_manual(scale_bar_um=10.0, scale_bar_px=-10)

    def test_invalid_scale_bar_um(self):
        """Test that zero or negative micrometer value raises error."""
        with pytest.raises(ValueError):
            calibrate_manual(scale_bar_um=0, scale_bar_px=100)

        with pytest.raises(ValueError):
            calibrate_manual(scale_bar_um=-10, scale_bar_px=100)


class TestEstimatedCalibration:
    """Tests for estimated 700x calibration."""

    def test_default_estimation(self):
        """Test default 700x estimation."""
        cal = estimate_calibration_700x()

        # Should return reasonable values for 700x magnification
        assert 0.1 < cal.um_per_pixel < 0.2
        assert cal.method == "estimated"
        assert cal.scale_bar_length_um == 10.0

    def test_different_image_widths(self):
        """Test estimation with different image widths."""
        cal_1024 = estimate_calibration_700x(1024)
        cal_2048 = estimate_calibration_700x(2048)

        # Same µm/pixel ratio regardless of image size
        # (field of view scales with image size)
        assert abs(cal_1024.um_per_pixel - cal_2048.um_per_pixel) < 0.01


class TestMagnificationCalibration:
    """Tests for magnification-based calibration."""

    def test_700x_magnification(self):
        """Test calibration at 700x magnification."""
        cal = calibrate_from_known_magnification(
            magnification=700,
            image_width_px=1024,
        )

        # At 700x with 10mm detector, FOV = 10/700 mm = 14.3 µm
        # For 1024 pixels, um_per_pixel ≈ 0.014
        assert 0.01 < cal.um_per_pixel < 0.02
        assert "700x" in cal.method

    def test_different_magnifications(self):
        """Test that higher magnification gives smaller um/pixel."""
        cal_500x = calibrate_from_known_magnification(500, 1024)
        cal_1000x = calibrate_from_known_magnification(1000, 1024)

        # Higher magnification = smaller field of view = smaller um/pixel
        assert cal_1000x.um_per_pixel < cal_500x.um_per_pixel
