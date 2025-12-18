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


# =============================================================================
# MCP Server Test Fixtures
# =============================================================================

@pytest.fixture
def flask_app(tmp_path):
    """Create Flask app with test config."""
    from fish_scale_ui.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['APP_ROOT'] = tmp_path
    app.config['UPLOAD_FOLDER'] = tmp_path / 'uploads'
    app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)
    return app


@pytest.fixture
def client(flask_app):
    """Flask test client."""
    return flask_app.test_client()


@pytest.fixture
def app_context(flask_app):
    """Flask application context."""
    with flask_app.app_context():
        yield


@pytest.fixture
def mcp_test_image(test_images_dir, tmp_path):
    """Copy a test image to temp location for MCP tests."""
    import shutil
    src = test_images_dir / "P1_Fig3_Lepisosteus_osseus_3.79um.tif"
    if src.exists():
        dst = tmp_path / src.name
        shutil.copy(src, dst)
        return dst
    return None


@pytest.fixture
def sample_tubercles():
    """Sample tubercle data for testing."""
    return [
        {'id': 1, 'centroid_x': 100.0, 'centroid_y': 100.0, 'radius_px': 10.0,
         'diameter_px': 20.0, 'diameter_um': 3.3, 'circularity': 0.95},
        {'id': 2, 'centroid_x': 150.0, 'centroid_y': 100.0, 'radius_px': 10.0,
         'diameter_px': 20.0, 'diameter_um': 3.3, 'circularity': 0.95},
        {'id': 3, 'centroid_x': 125.0, 'centroid_y': 150.0, 'radius_px': 10.0,
         'diameter_px': 20.0, 'diameter_um': 3.3, 'circularity': 0.95},
    ]


@pytest.fixture
def sample_edges():
    """Sample edge/connection data for testing."""
    return [
        {'id1': 1, 'id2': 2, 'x1': 100.0, 'y1': 100.0, 'x2': 150.0, 'y2': 100.0,
         'center_distance_um': 8.25, 'edge_distance_um': 5.0},
        {'id1': 1, 'id2': 3, 'x1': 100.0, 'y1': 100.0, 'x2': 125.0, 'y2': 150.0,
         'center_distance_um': 9.35, 'edge_distance_um': 6.1},
        {'id1': 2, 'id2': 3, 'x1': 150.0, 'y1': 100.0, 'x2': 125.0, 'y2': 150.0,
         'center_distance_um': 9.35, 'edge_distance_um': 6.1},
    ]


@pytest.fixture
def sample_calibration():
    """Sample calibration data."""
    return {'um_per_px': 0.165, 'method': 'manual'}


@pytest.fixture
def synthetic_test_image(tmp_path):
    """Create a synthetic grayscale PNG image for testing."""
    from PIL import Image
    import numpy as np

    # Create a 256x256 grayscale image
    data = np.random.randint(100, 200, (256, 256), dtype=np.uint8)
    img = Image.fromarray(data, mode='L')

    image_path = tmp_path / 'test_image.png'
    img.save(image_path)
    return image_path
