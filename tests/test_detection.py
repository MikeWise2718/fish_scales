"""Tests for detection module."""

import numpy as np
import pytest
from fish_scale_analysis.core.calibration import calibrate_manual
from fish_scale_analysis.core.detection import (
    detect_blobs_log,
    detect_blobs_dog,
    filter_by_size,
    filter_by_edge_distance,
    detect_tubercles,
)


@pytest.fixture
def simple_calibration():
    """Create a simple 1:1 calibration for testing."""
    return calibrate_manual(scale_bar_um=100.0, scale_bar_px=100.0)


@pytest.fixture
def image_with_blobs():
    """Create a test image with known blob positions."""
    image = np.zeros((200, 200), dtype=np.float64)

    # Add circular blobs at known positions
    blob_params = [
        (50, 50, 10),   # (x, y, radius)
        (100, 50, 12),
        (150, 50, 8),
        (50, 100, 11),
        (100, 100, 10),
        (150, 100, 9),
        (50, 150, 10),
        (100, 150, 10),
        (150, 150, 10),
    ]

    y, x = np.ogrid[:200, :200]

    for cx, cy, r in blob_params:
        dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        blob = np.exp(-(dist ** 2) / (2 * (r / 2) ** 2))
        image += blob * 0.8

    image = np.clip(image, 0, 1)
    return image, blob_params


class TestBlobDetection:
    """Tests for blob detection algorithms."""

    def test_log_detects_blobs(self, image_with_blobs):
        """Test that LoG detects blobs."""
        image, expected = image_with_blobs

        blobs = detect_blobs_log(
            image,
            min_sigma=2,
            max_sigma=10,
            threshold=0.1,
        )

        # Should detect approximately the right number
        assert len(blobs) >= len(expected) * 0.5  # Allow some misses
        assert len(blobs) <= len(expected) * 2    # Not too many false positives

    def test_dog_detects_blobs(self, image_with_blobs):
        """Test that DoG detects blobs."""
        image, expected = image_with_blobs

        blobs = detect_blobs_dog(
            image,
            min_sigma=2,
            max_sigma=10,
            threshold=0.1,
        )

        assert len(blobs) >= len(expected) * 0.5
        assert len(blobs) <= len(expected) * 2

    def test_blob_format(self, image_with_blobs):
        """Test that blobs have correct format [y, x, sigma]."""
        image, _ = image_with_blobs
        blobs = detect_blobs_log(image, min_sigma=2, max_sigma=10, threshold=0.1)

        if len(blobs) > 0:
            assert blobs.shape[1] == 3  # [y, x, sigma]
            assert all(blobs[:, 0] >= 0)  # y >= 0
            assert all(blobs[:, 1] >= 0)  # x >= 0
            assert all(blobs[:, 2] > 0)   # sigma > 0


class TestSizeFiltering:
    """Tests for size-based filtering."""

    def test_filter_small_blobs(self, simple_calibration):
        """Test filtering of blobs below minimum size."""
        # Create blobs with varying sizes
        blobs = np.array([
            [50, 50, 1],   # Small (diameter ~2.8 µm)
            [100, 100, 5],  # Medium (diameter ~14 µm)
            [150, 150, 10], # Large (diameter ~28 µm)
        ], dtype=np.float64)

        # Filter to only medium-sized blobs (5-20 µm)
        filtered = filter_by_size(
            blobs,
            simple_calibration,
            min_diameter_um=5.0,
            max_diameter_um=20.0,
        )

        assert len(filtered) == 1
        assert filtered[0, 2] == 5  # The medium one

    def test_empty_input(self, simple_calibration):
        """Test handling of empty blob array."""
        blobs = np.array([]).reshape(0, 3)
        filtered = filter_by_size(blobs, simple_calibration)
        assert len(filtered) == 0


class TestEdgeFiltering:
    """Tests for edge distance filtering."""

    def test_filter_edge_blobs(self):
        """Test that blobs near edges are filtered out."""
        blobs = np.array([
            [5, 100, 5],    # Too close to top edge
            [195, 100, 5],  # Too close to bottom edge
            [100, 5, 5],    # Too close to left edge
            [100, 195, 5],  # Too close to right edge
            [100, 100, 5],  # In the center - should remain
        ], dtype=np.float64)

        filtered = filter_by_edge_distance(
            blobs,
            image_shape=(200, 200),
            min_edge_distance_px=10,
        )

        assert len(filtered) == 1
        assert filtered[0, 0] == 100  # y
        assert filtered[0, 1] == 100  # x


class TestTubercleDetection:
    """Tests for complete tubercle detection."""

    def test_detect_tubercles(self, image_with_blobs, simple_calibration):
        """Test complete tubercle detection pipeline."""
        image, expected = image_with_blobs

        tubercles = detect_tubercles(
            image,
            simple_calibration,
            min_diameter_um=5.0,
            max_diameter_um=30.0,
            threshold=0.1,
            min_circularity=0.3,
        )

        # Should detect some tubercles
        assert len(tubercles) > 0

        # Check tubercle properties
        for t in tubercles:
            assert t.id > 0
            assert t.diameter_um > 0
            assert t.diameter_px > 0
            assert 0 <= t.circularity <= 1

    def test_tubercle_positions(self, image_with_blobs, simple_calibration):
        """Test that detected positions are reasonable."""
        image, expected = image_with_blobs

        tubercles = detect_tubercles(
            image,
            simple_calibration,
            min_diameter_um=5.0,
            max_diameter_um=30.0,
            threshold=0.1,
        )

        # Check that detected positions are within image bounds
        h, w = image.shape
        for t in tubercles:
            assert 0 <= t.centroid[0] < w  # x
            assert 0 <= t.centroid[1] < h  # y

    def test_no_detections_on_blank(self, simple_calibration):
        """Test that blank image yields no detections."""
        blank = np.zeros((200, 200), dtype=np.float64)

        tubercles = detect_tubercles(
            blank,
            simple_calibration,
            threshold=0.1,
        )

        assert len(tubercles) == 0
