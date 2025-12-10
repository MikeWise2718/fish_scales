"""Integration tests for fish scale analysis against test images."""

import pytest
from pathlib import Path

from fish_scale_analysis.core.measurement import process_image


# Test tolerances from test_cases.md
DIAMETER_TOLERANCE = 0.5  # µm
SPACING_TOLERANCE = 0.7   # µm


class TestIntegration:
    """Integration tests against known test images."""

    @pytest.mark.parametrize("test_case", [
        ("P1_Fig1_Lepidotes_elvensis_4.78um.tif", 4.78, 4.57),
        ("P1_Fig2_Polypterus_bichir_2.63um.tif", 2.63, 6.19),
        ("P1_Fig3_Lepisosteus_osseus_3.79um.tif", 3.79, 3.14),
        ("P1_Fig4_Atractosteus_simplex_7.07um.tif", 7.07, 2.61),
        ("P1_Fig5_Lepisosteidae_indet_Portugal_3.82um.tif", 3.82, 3.82),
        ("P1_Fig6_Lepisosteidae_indet_Bolivia_4.50um.tif", 4.50, 4.40),
        ("P2_Pl1_Fig1a_Lepisosteus_platostomus_5.38um.tif", 5.38, 3.59),
        ("P2_Pl1_Fig1b_Polypterus_ornatipinnis_2.81um.tif", 2.81, 5.97),
        ("P3_Fig4_Obaichthys_laevis_5.0um.tif", 5.0, 4.67),
        ("P3_Fig5_Obaichthys_decoratus_5.0um.tif", 5.0, 4.67),
    ])
    def test_measurement_accuracy(self, test_images_dir, test_case):
        """Test that measurements fall within acceptable tolerances."""
        filename, expected_diameter, expected_spacing = test_case
        image_path = test_images_dir / filename

        if not image_path.exists():
            pytest.skip(f"Test image not found: {filename}")

        # Process image
        result, _, _ = process_image(image_path)

        # Check diameter tolerance
        diameter_error = abs(result.mean_diameter_um - expected_diameter)
        assert diameter_error <= DIAMETER_TOLERANCE, (
            f"Diameter error {diameter_error:.2f} µm exceeds tolerance {DIAMETER_TOLERANCE} µm "
            f"(expected {expected_diameter}, got {result.mean_diameter_um:.2f})"
        )

        # Check spacing tolerance
        spacing_error = abs(result.mean_space_um - expected_spacing)
        assert spacing_error <= SPACING_TOLERANCE, (
            f"Spacing error {spacing_error:.2f} µm exceeds tolerance {SPACING_TOLERANCE} µm "
            f"(expected {expected_spacing}, got {result.mean_space_um:.2f})"
        )

    @pytest.mark.parametrize("test_case", [
        ("P1_Fig2_Polypterus_bichir_2.63um.tif", "Polypterus"),
        ("P1_Fig3_Lepisosteus_osseus_3.79um.tif", "Lepisosteus"),
        ("P1_Fig4_Atractosteus_simplex_7.07um.tif", "Atractosteus"),
    ])
    def test_genus_classification(self, test_images_dir, test_case):
        """Test that genus classification is correct for clear cases."""
        filename, expected_genus = test_case
        image_path = test_images_dir / filename

        if not image_path.exists():
            pytest.skip(f"Test image not found: {filename}")

        result, _, _ = process_image(image_path)

        assert result.suggested_genus == expected_genus, (
            f"Expected genus {expected_genus}, got {result.suggested_genus}"
        )

    def test_minimum_tubercle_detection(self, test_images_dir):
        """Test that enough tubercles are detected for statistical validity."""
        # Use a known good image
        image_path = test_images_dir / "P1_Fig3_Lepisosteus_osseus_3.79um.tif"

        if not image_path.exists():
            pytest.skip("Test image not found")

        result, _, _ = process_image(image_path)

        # Should detect at least 10 tubercles for valid statistics
        assert result.n_tubercles >= 10, (
            f"Only {result.n_tubercles} tubercles detected, need at least 10"
        )

    def test_output_completeness(self, test_images_dir):
        """Test that all output fields are populated."""
        image_path = test_images_dir / "P1_Fig3_Lepisosteus_osseus_3.79um.tif"

        if not image_path.exists():
            pytest.skip("Test image not found")

        result, preprocessed, info = process_image(image_path)

        # Check result fields
        assert result.image_path != ""
        assert result.calibration is not None
        assert result.n_tubercles > 0
        assert len(result.tubercles) > 0
        assert len(result.neighbor_edges) > 0
        assert len(result.tubercle_diameters_um) > 0
        assert len(result.intertubercular_spaces_um) > 0
        assert result.mean_diameter_um > 0
        assert result.mean_space_um > 0
        assert result.suggested_genus is not None

        # Check preprocessed image
        assert preprocessed is not None
        assert preprocessed.shape[0] > 0
        assert preprocessed.shape[1] > 0

        # Check info dict
        assert "image_path" in info
        assert "image_shape" in info
        assert "n_tubercles_detected" in info


class TestRealImages:
    """Tests against real sample images in the images/ directory."""

    def test_real_image_processing(self):
        """Test processing of real images from the images directory."""
        images_dir = Path(__file__).parent.parent / "images"

        if not images_dir.exists():
            pytest.skip("Images directory not found")

        image_files = list(images_dir.glob("*.tif")) + list(images_dir.glob("*.tiff"))

        if not image_files:
            pytest.skip("No TIFF images found in images directory")

        for image_path in image_files[:3]:  # Test first 3 images
            result, _, _ = process_image(image_path)

            # Basic sanity checks
            assert result is not None
            assert result.calibration is not None

            # Results should be in reasonable ranges
            if result.n_tubercles > 0:
                assert 1.0 <= result.mean_diameter_um <= 15.0, (
                    f"Unusual diameter {result.mean_diameter_um} for {image_path.name}"
                )
