"""Tests for Tools API Flask endpoints (/api/tools/*)."""

import json
import pytest
from pathlib import Path


def reset_api_state():
    """Reset the module-level state between tests."""
    from fish_scale_ui.routes import api
    api._current_image.update({
        'path': None,
        'web_path': None,
        'filename': None,
        'rotation': 0,
        'calibration': None,
        'annotations_saved': False,
    })
    api._extraction_data.update({
        'tubercles': [],
        'edges': [],
        'statistics': {},
        'parameters': {},
        'dirty': False,
    })


@pytest.fixture(autouse=True)
def reset_state():
    """Reset API state before each test."""
    reset_api_state()
    yield
    reset_api_state()


class TestStateEndpoint:
    """Tests for /api/tools/state endpoint."""

    def test_state_no_image(self, client):
        """State endpoint returns loaded=False when no image."""
        response = client.get('/api/tools/state')
        assert response.status_code == 200
        data = response.get_json()
        assert data['image']['loaded'] is False
        assert data['tubercles'] == []
        assert data['edges'] == []

    def test_state_with_image(self, client, synthetic_test_image):
        """State endpoint returns complete state with loaded image."""
        # Load an image first
        response = client.post('/api/tools/load-image',
                               json={'path': str(synthetic_test_image)})
        assert response.status_code == 200

        # Now check state
        response = client.get('/api/tools/state')
        assert response.status_code == 200
        data = response.get_json()
        assert data['image']['loaded'] is True
        assert data['image']['width'] == 256
        assert data['image']['height'] == 256


class TestScreenshotEndpoint:
    """Tests for /api/tools/screenshot endpoint."""

    def test_screenshot_no_image_loaded(self, client):
        """Screenshot returns 400 when no image loaded."""
        response = client.get('/api/tools/screenshot')
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_screenshot_with_image(self, client, synthetic_test_image):
        """Screenshot returns base64 PNG when image loaded."""
        # Load image
        client.post('/api/tools/load-image', json={'path': str(synthetic_test_image)})

        # Get screenshot
        response = client.get('/api/tools/screenshot')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'image_b64' in data
        assert len(data['image_b64']) > 0
        assert data['width'] == 256
        assert data['height'] == 256

    def test_screenshot_overlay_options(self, client, synthetic_test_image):
        """Screenshot respects overlay options."""
        client.post('/api/tools/load-image', json={'path': str(synthetic_test_image)})

        # Test with overlay disabled
        response = client.get('/api/tools/screenshot?overlay=false')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # Test with numbers enabled
        response = client.get('/api/tools/screenshot?numbers=true')
        assert response.status_code == 200


class TestCalibrationEndpoint:
    """Tests for /api/tools/calibration endpoint."""

    def test_calibration_get_none(self, client):
        """Calibration GET returns None when not set."""
        response = client.get('/api/tools/calibration')
        assert response.status_code == 200
        data = response.get_json()
        assert data['calibration'] is None

    def test_calibration_set_um_per_px(self, client):
        """Calibration can be set directly as um_per_px."""
        response = client.post('/api/tools/calibration',
                               json={'um_per_px': 0.165})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['calibration']['um_per_px'] == 0.165
        assert data['calibration']['method'] == 'manual'

    def test_calibration_set_scale_bar(self, client):
        """Calibration can be set from scale bar measurements."""
        response = client.post('/api/tools/calibration',
                               json={'scale_um': 100, 'scale_px': 200})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['calibration']['um_per_px'] == 0.5
        assert data['calibration']['method'] == 'scale_bar'

    def test_calibration_missing_params(self, client):
        """Calibration returns 400 with missing params."""
        response = client.post('/api/tools/calibration', json={})
        assert response.status_code == 400


class TestParamsEndpoint:
    """Tests for /api/tools/params endpoint."""

    def test_params_get_default(self, client):
        """Params GET returns current parameters."""
        response = client.get('/api/tools/params')
        assert response.status_code == 200
        data = response.get_json()
        assert 'parameters' in data

    def test_params_set_partial(self, client):
        """Params POST updates only provided values."""
        response = client.post('/api/tools/params',
                               json={'threshold': 0.1, 'method': 'log'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['parameters']['threshold'] == 0.1
        assert data['parameters']['method'] == 'log'

    def test_params_set_all(self, client):
        """Params POST can set all parameters."""
        params = {
            'method': 'dog',
            'threshold': 0.05,
            'min_diameter_um': 2.0,
            'max_diameter_um': 15.0,
            'min_circularity': 0.6,
            'clahe_clip': 0.04,
            'clahe_kernel': 8,
            'blur_sigma': 1.5,
            'neighbor_graph': 'gabriel',
        }
        response = client.post('/api/tools/params', json=params)
        assert response.status_code == 200
        data = response.get_json()
        for key, value in params.items():
            assert data['parameters'][key] == value


class TestTubercleEndpoint:
    """Tests for /api/tools/tubercle endpoint."""

    def test_tubercle_add_no_calibration(self, client):
        """Adding tubercle without calibration returns 400."""
        response = client.post('/api/tools/tubercle',
                               json={'x': 100, 'y': 100, 'radius': 10})
        assert response.status_code == 400
        assert 'Calibration' in response.get_json()['error']

    def test_tubercle_add_with_radius(self, client):
        """Add tubercle with explicit radius."""
        # Set calibration first
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})

        response = client.post('/api/tools/tubercle',
                               json={'x': 100.0, 'y': 100.0, 'radius': 15.0})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['tubercle']['centroid_x'] == 100.0
        assert data['tubercle']['centroid_y'] == 100.0
        assert data['tubercle']['radius_px'] == 15.0
        assert data['id'] == 1

    def test_tubercle_add_auto_radius(self, client, sample_tubercles):
        """Add tubercle with auto-calculated radius from existing."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})

        # Add some existing tubercles
        api._extraction_data['tubercles'] = sample_tubercles.copy()

        response = client.post('/api/tools/tubercle',
                               json={'x': 200.0, 'y': 200.0})
        assert response.status_code == 200
        data = response.get_json()
        # Radius should be mean of existing (all 10.0)
        assert data['tubercle']['radius_px'] == 10.0

    def test_tubercle_add_missing_coords(self, client):
        """Add tubercle without coords returns 400."""
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        response = client.post('/api/tools/tubercle', json={'radius': 10})
        assert response.status_code == 400

    def test_tubercle_move(self, client, sample_tubercles):
        """Move an existing tubercle."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()

        response = client.put('/api/tools/tubercle',
                              json={'id': 1, 'x': 200.0, 'y': 200.0})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['tubercle']['centroid_x'] == 200.0
        assert data['tubercle']['centroid_y'] == 200.0

    def test_tubercle_move_not_found(self, client):
        """Move non-existent tubercle returns 404."""
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        response = client.put('/api/tools/tubercle',
                              json={'id': 999, 'x': 200.0, 'y': 200.0})
        assert response.status_code == 404

    def test_tubercle_delete(self, client, sample_tubercles, sample_edges):
        """Delete tubercle and its connections."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()
        api._extraction_data['edges'] = sample_edges.copy()

        response = client.delete('/api/tools/tubercle', json={'id': 1})
        assert response.status_code == 200
        assert response.get_json()['success'] is True

        # Verify tubercle removed
        assert len(api._extraction_data['tubercles']) == 2
        # Verify connections involving id=1 removed
        for edge in api._extraction_data['edges']:
            assert edge['id1'] != 1 and edge['id2'] != 1

    def test_tubercle_delete_not_found(self, client):
        """Delete non-existent tubercle returns 404."""
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        response = client.delete('/api/tools/tubercle', json={'id': 999})
        assert response.status_code == 404


class TestConnectionEndpoint:
    """Tests for /api/tools/connection endpoint."""

    def test_connection_add(self, client, sample_tubercles):
        """Add connection between two tubercles."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()

        response = client.post('/api/tools/connection',
                               json={'id1': 1, 'id2': 2})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['connection']['id1'] == 1
        assert data['connection']['id2'] == 2
        assert 'center_distance_um' in data['connection']
        assert 'edge_distance_um' in data['connection']

    def test_connection_add_duplicate(self, client, sample_tubercles, sample_edges):
        """Add duplicate connection returns 400."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()
        api._extraction_data['edges'] = sample_edges.copy()

        response = client.post('/api/tools/connection',
                               json={'id1': 1, 'id2': 2})
        assert response.status_code == 400
        assert 'already exists' in response.get_json()['error']

    def test_connection_add_missing_tubercle(self, client, sample_tubercles):
        """Add connection with missing tubercle returns 404."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()

        response = client.post('/api/tools/connection',
                               json={'id1': 1, 'id2': 999})
        assert response.status_code == 404

    def test_connection_delete(self, client, sample_tubercles, sample_edges):
        """Delete an existing connection."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()
        api._extraction_data['edges'] = sample_edges.copy()

        response = client.delete('/api/tools/connection',
                                 json={'id1': 1, 'id2': 2})
        assert response.status_code == 200
        assert response.get_json()['success'] is True

    def test_connection_delete_not_found(self, client, sample_tubercles):
        """Delete non-existent connection returns 404."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()

        response = client.delete('/api/tools/connection',
                                 json={'id1': 1, 'id2': 2})
        assert response.status_code == 404


class TestConnectionsClearEndpoint:
    """Tests for /api/tools/connections/clear endpoint."""

    def test_connections_clear(self, client, sample_edges):
        """Clear all connections."""
        from fish_scale_ui.routes import api
        api._extraction_data['edges'] = sample_edges.copy()

        response = client.post('/api/tools/connections/clear')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['removed_count'] == 3
        assert api._extraction_data['edges'] == []

    def test_connections_clear_empty(self, client):
        """Clear when no connections returns 0 removed."""
        response = client.post('/api/tools/connections/clear')
        assert response.status_code == 200
        data = response.get_json()
        assert data['removed_count'] == 0


class TestAutoConnectEndpoint:
    """Tests for /api/tools/auto-connect endpoint."""

    def test_auto_connect_no_calibration(self, client):
        """Auto-connect without calibration returns 400."""
        response = client.post('/api/tools/auto-connect', json={'method': 'gabriel'})
        assert response.status_code == 400

    def test_auto_connect_insufficient_tubercles(self, client):
        """Auto-connect with <2 tubercles returns 400."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = [{'id': 1, 'centroid_x': 100, 'centroid_y': 100}]

        response = client.post('/api/tools/auto-connect', json={'method': 'gabriel'})
        assert response.status_code == 400

    def test_auto_connect_gabriel(self, client, sample_tubercles):
        """Auto-connect with Gabriel graph."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()

        response = client.post('/api/tools/auto-connect', json={'method': 'gabriel'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['n_edges'] > 0
        assert len(data['edges']) == data['n_edges']

    def test_auto_connect_delaunay(self, client, sample_tubercles):
        """Auto-connect with Delaunay triangulation."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()

        response = client.post('/api/tools/auto-connect', json={'method': 'delaunay'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        # Delaunay on 3 points = 3 edges (triangle)
        assert data['n_edges'] == 3

    def test_auto_connect_rng(self, client, sample_tubercles):
        """Auto-connect with RNG graph."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()

        response = client.post('/api/tools/auto-connect', json={'method': 'rng'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_auto_connect_invalid_method(self, client, sample_tubercles):
        """Auto-connect with invalid method returns 400."""
        from fish_scale_ui.routes import api
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})
        api._extraction_data['tubercles'] = sample_tubercles.copy()

        response = client.post('/api/tools/auto-connect', json={'method': 'invalid'})
        assert response.status_code == 400


class TestStatisticsEndpoint:
    """Tests for /api/tools/statistics endpoint."""

    def test_statistics_empty(self, client):
        """Statistics with no data."""
        response = client.get('/api/tools/statistics')
        assert response.status_code == 200
        data = response.get_json()
        assert data['n_tubercles'] == 0
        assert data['n_edges'] == 0

    def test_statistics_with_data(self, client, sample_tubercles, sample_edges):
        """Statistics with tubercles and edges."""
        from fish_scale_ui.routes import api
        api._extraction_data['tubercles'] = sample_tubercles.copy()
        api._extraction_data['edges'] = sample_edges.copy()

        response = client.get('/api/tools/statistics')
        assert response.status_code == 200
        data = response.get_json()
        assert data['n_tubercles'] == 3
        assert data['n_edges'] == 3
        assert 'mean_diameter_um' in data
        assert 'std_diameter_um' in data
        assert 'mean_space_um' in data
        assert 'std_space_um' in data

    def test_statistics_genus_classification(self, client, sample_tubercles, sample_edges):
        """Statistics includes genus suggestion."""
        from fish_scale_ui.routes import api
        api._extraction_data['tubercles'] = sample_tubercles.copy()
        api._extraction_data['edges'] = sample_edges.copy()

        response = client.get('/api/tools/statistics')
        data = response.get_json()
        assert 'suggested_genus' in data
        assert 'classification_confidence' in data


class TestLoadImageEndpoint:
    """Tests for /api/tools/load-image endpoint."""

    def test_load_image_success(self, client, synthetic_test_image):
        """Load image successfully."""
        response = client.post('/api/tools/load-image',
                               json={'path': str(synthetic_test_image)})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['filename'] == 'test_image.png'
        assert data['width'] == 256
        assert data['height'] == 256

    def test_load_image_not_found(self, client):
        """Load non-existent image returns 404."""
        response = client.post('/api/tools/load-image',
                               json={'path': '/nonexistent/image.png'})
        assert response.status_code == 404

    def test_load_image_missing_path(self, client):
        """Load image without path returns 400."""
        response = client.post('/api/tools/load-image', json={})
        assert response.status_code == 400


class TestSaveEndpoint:
    """Tests for /api/tools/save endpoint."""

    def test_save_no_image(self, client):
        """Save without image returns 400."""
        response = client.post('/api/tools/save')
        assert response.status_code == 400

    def test_save_no_data(self, client, synthetic_test_image):
        """Save without tubercle data returns 400."""
        client.post('/api/tools/load-image', json={'path': str(synthetic_test_image)})
        response = client.post('/api/tools/save')
        assert response.status_code == 400

    def test_save_success(self, client, synthetic_test_image, sample_tubercles, tmp_path):
        """Save annotations file successfully."""
        from fish_scale_ui.routes import api

        # Load image
        client.post('/api/tools/load-image', json={'path': str(synthetic_test_image)})

        # Set calibration
        client.post('/api/tools/calibration', json={'um_per_px': 0.165})

        # Add tubercles
        api._extraction_data['tubercles'] = sample_tubercles.copy()
        api._extraction_data['statistics'] = {'n_tubercles': 3}

        # Save
        response = client.post('/api/tools/save')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
