"""Tests for preprocessing module."""

import numpy as np
import pytest
from fish_scale_analysis.core.preprocessing import (
    to_grayscale,
    apply_clahe,
    apply_gaussian_blur,
    apply_morphological_opening,
    normalize_image,
    preprocess_pipeline,
    get_image_info,
)


class TestGrayscaleConversion:
    """Tests for grayscale conversion."""

    def test_already_grayscale(self):
        """Test that grayscale image passes through."""
        gray = np.random.rand(100, 100)
        result = to_grayscale(gray)

        assert result.shape == gray.shape
        assert result.dtype == np.float64

    def test_rgb_conversion(self):
        """Test RGB to grayscale conversion."""
        rgb = np.random.rand(100, 100, 3)
        result = to_grayscale(rgb)

        assert result.shape == (100, 100)
        assert result.dtype == np.float64


class TestCLAHE:
    """Tests for CLAHE enhancement."""

    def test_output_range(self, sample_grayscale_image):
        """Test that CLAHE output is in valid range."""
        result = apply_clahe(sample_grayscale_image)

        assert result.min() >= 0
        assert result.max() <= 1

    def test_output_shape(self, sample_grayscale_image):
        """Test that CLAHE preserves shape."""
        result = apply_clahe(sample_grayscale_image)
        assert result.shape == sample_grayscale_image.shape

    def test_contrast_enhancement(self):
        """Test that CLAHE increases contrast."""
        # Create a low-contrast image
        low_contrast = np.ones((100, 100)) * 0.5
        low_contrast[40:60, 40:60] = 0.55

        result = apply_clahe(low_contrast, clip_limit=0.1)

        # Result should have higher contrast (larger std)
        assert result.std() >= low_contrast.std()


class TestGaussianBlur:
    """Tests for Gaussian blur."""

    def test_smoothing_effect(self, sample_grayscale_image):
        """Test that blur reduces high-frequency noise."""
        # Add high-frequency noise
        noisy = sample_grayscale_image + np.random.normal(0, 0.1, sample_grayscale_image.shape)
        noisy = np.clip(noisy, 0, 1)

        result = apply_gaussian_blur(noisy, sigma=2.0)

        # Blurred image should have lower gradient magnitude
        grad_noisy = np.gradient(noisy)
        grad_result = np.gradient(result)

        noisy_grad_mag = np.sqrt(grad_noisy[0] ** 2 + grad_noisy[1] ** 2).mean()
        result_grad_mag = np.sqrt(grad_result[0] ** 2 + grad_result[1] ** 2).mean()

        assert result_grad_mag < noisy_grad_mag

    def test_shape_preserved(self, sample_grayscale_image):
        """Test that blur preserves shape."""
        result = apply_gaussian_blur(sample_grayscale_image)
        assert result.shape == sample_grayscale_image.shape


class TestMorphologicalOpening:
    """Tests for morphological opening."""

    def test_removes_small_features(self):
        """Test that opening removes small bright spots."""
        # Create image with small and large spots
        image = np.zeros((100, 100))
        image[20, 20] = 1  # Small spot (1 pixel)
        image[45:55, 45:55] = 1  # Large spot (10x10)

        result = apply_morphological_opening(image, disk_radius=3)

        # Small spot should be removed
        assert result[20, 20] < 0.5
        # Large spot should remain
        assert result[50, 50] > 0.5

    def test_shape_preserved(self, sample_grayscale_image):
        """Test that opening preserves shape."""
        result = apply_morphological_opening(sample_grayscale_image)
        assert result.shape == sample_grayscale_image.shape


class TestNormalization:
    """Tests for image normalization."""

    def test_output_range(self):
        """Test that normalized image is in [0, 1] range."""
        image = np.random.rand(100, 100) * 100 + 50  # Range [50, 150]
        result = normalize_image(image)

        assert abs(result.min()) < 1e-10
        assert abs(result.max() - 1.0) < 1e-10

    def test_constant_image(self):
        """Test normalization of constant image."""
        constant = np.ones((100, 100)) * 0.5
        result = normalize_image(constant)

        # Should return zeros for constant image
        assert result.max() == 0


class TestPreprocessPipeline:
    """Tests for complete preprocessing pipeline."""

    def test_pipeline_output(self, sample_grayscale_image):
        """Test that pipeline produces valid output."""
        result, intermediates = preprocess_pipeline(sample_grayscale_image)

        assert result.shape == sample_grayscale_image.shape
        assert result.min() >= 0
        assert result.max() <= 1

    def test_intermediates_captured(self, sample_grayscale_image):
        """Test that intermediate images are captured."""
        result, intermediates = preprocess_pipeline(sample_grayscale_image)

        assert "original" in intermediates
        assert "grayscale" in intermediates
        assert "clahe" in intermediates
        assert "blurred" in intermediates
        assert "final" in intermediates


class TestImageInfo:
    """Tests for image info function."""

    def test_info_contents(self, sample_grayscale_image):
        """Test that info contains expected keys."""
        info = get_image_info(sample_grayscale_image)

        assert "shape" in info
        assert "dtype" in info
        assert "min" in info
        assert "max" in info
        assert "mean" in info
        assert "std" in info
