"""Pytest fixtures for fish scale analysis tests."""

import numpy as np
import pytest
from pathlib import Path

# Path to test images directory
TEST_IMAGES_DIR = Path(__file__).parent.parent / "test_images"


@pytest.fixture
def test_images_dir():
    """Return path to test images directory."""
    return TEST_IMAGES_DIR


@pytest.fixture
def sample_grayscale_image():
    """Create a sample grayscale image for testing."""
    # Create a 256x256 grayscale image with some circular blobs
    image = np.zeros((256, 256), dtype=np.float64)

    # Add some circular blobs
    centers = [(50, 50), (100, 100), (150, 150), (50, 150), (150, 50)]
    radii = [8, 10, 9, 7, 11]

    y, x = np.ogrid[:256, :256]

    for (cx, cy), r in zip(centers, radii):
        mask = (x - cx) ** 2 + (y - cy) ** 2 <= r ** 2
        image[mask] = 0.8

    # Add some noise
    image += np.random.normal(0, 0.05, image.shape)
    image = np.clip(image, 0, 1)

    return image


@pytest.fixture
def synthetic_tubercle_image():
    """Create a synthetic image with known tubercle positions."""
    # Create a 512x512 image with regularly spaced bright spots
    image = np.ones((512, 512), dtype=np.float64) * 0.2

    # Add tubercles in a grid pattern
    tubercle_positions = []
    diameter = 20  # pixels

    for row in range(3, 10):
        for col in range(3, 10):
            cx = col * 50
            cy = row * 50
            tubercle_positions.append((cx, cy))

            y, x = np.ogrid[:512, :512]
            dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)

            # Create a smooth circular blob
            blob = np.exp(-(dist ** 2) / (2 * (diameter / 4) ** 2))
            image += blob * 0.6

    image = np.clip(image, 0, 1)

    return image, tubercle_positions, diameter


@pytest.fixture
def expected_test_cases():
    """Return expected values for test images."""
    return [
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
    ]
