# MCP Server Testing Strategy

## Overview

This document outlines the testing strategy for the MCP server (`fish_scale_mcp`) and its Flask API endpoints (`fish_scale_ui/routes/mcp_api.py`).

## Test Files

| File | Purpose | Priority |
|------|---------|----------|
| `tests/test_mcp_api.py` | Flask endpoint tests | 1 - Critical |
| `tests/test_mcp_screenshot.py` | Server-side rendering tests | 2 - Important |
| `tests/test_mcp_server.py` | MCP tool registration/parameters | 3 - Medium |
| `tests/test_mcp_integration.py` | End-to-end workflow tests | 4 - Nice to have |

---

## 1. Flask API Tests (`tests/test_mcp_api.py`)

Test the Flask endpoints directly using Flask test client.

### Fixtures Required
- `app` - Flask app with test config
- `client` - Flask test client
- `loaded_image_client` - Client with an image already loaded

### Test Cases

#### State & Screenshot Endpoints
- `test_screenshot_no_image_loaded()` - Should return 400
- `test_screenshot_with_image()` - Returns base64 PNG
- `test_screenshot_overlay_options()` - Test overlay/numbers/scale_bar params
- `test_state_no_image()` - Returns loaded=False
- `test_state_with_image()` - Returns complete state

#### Parameter Endpoints
- `test_params_get_default()` - Get default parameters
- `test_params_set_partial()` - Partial update works
- `test_params_set_invalid_method()` - Invalid method rejected

#### Calibration Endpoints
- `test_calibration_get_none()` - No calibration set
- `test_calibration_set_um_per_px()` - Direct µm/px setting
- `test_calibration_set_scale_bar()` - Calculate from scale bar

#### Tubercle CRUD
- `test_tubercle_add_with_radius()` - Add with explicit radius
- `test_tubercle_add_auto_radius()` - Add with auto-calculated radius
- `test_tubercle_add_no_calibration()` - Should return 400
- `test_tubercle_move()` - Move existing tubercle
- `test_tubercle_move_not_found()` - Should return 404
- `test_tubercle_delete()` - Delete tubercle and its connections
- `test_tubercle_delete_not_found()` - Should return 404

#### Connection CRUD
- `test_connection_add()` - Add connection between tubercles
- `test_connection_add_duplicate()` - Should return 400
- `test_connection_add_missing_tubercle()` - Should return 404
- `test_connection_delete()` - Remove connection
- `test_connection_delete_not_found()` - Should return 404
- `test_connections_clear()` - Remove all connections

#### Auto-Connect
- `test_auto_connect_gabriel()` - Default method
- `test_auto_connect_delaunay()` - All edges
- `test_auto_connect_rng()` - Conservative edges
- `test_auto_connect_invalid_method()` - Should return 400
- `test_auto_connect_no_calibration()` - Should return 400
- `test_auto_connect_insufficient_tubercles()` - Should return 400

#### Statistics
- `test_statistics_empty()` - No tubercles
- `test_statistics_with_data()` - Returns computed stats
- `test_statistics_genus_classification()` - Includes genus suggestion

#### Save/Load
- `test_save_no_image()` - Should return 400
- `test_save_no_data()` - Should return 400
- `test_save_success()` - Creates SLO file
- `test_load_image_success()` - Loads and converts image
- `test_load_image_not_found()` - Should return 404

---

## 2. Screenshot Rendering Tests (`tests/test_mcp_screenshot.py`)

Test server-side rendering with PIL.

### Test Cases

#### Basic Rendering
- `test_render_screenshot_basic()` - Image only, no overlay
- `test_render_screenshot_returns_base64_png()` - Valid base64 PNG
- `test_render_screenshot_file_not_found()` - Raises FileNotFoundError

#### Overlay Options
- `test_render_with_tubercles()` - Draws cyan circles
- `test_render_with_connections()` - Draws green lines
- `test_render_with_numbers()` - Draws ID labels
- `test_render_with_scale_bar()` - Draws scale bar
- `test_render_selected_tubercle()` - Yellow highlight
- `test_render_selected_connection()` - Yellow highlight

#### Thumbnail
- `test_render_thumbnail()` - Resized image
- `test_render_thumbnail_maintains_aspect()` - Aspect ratio preserved

---

## 3. MCP Server Tests (`tests/test_mcp_server.py`)

Test MCP tool registration and parameter schemas.

### Test Cases

#### Tool Registration
- `test_server_creation()` - Server initializes
- `test_all_tools_registered()` - All 15+ tools present
- `test_tool_names()` - Correct tool names

#### Tool Schemas (spot checks)
- `test_get_screenshot_schema()` - Has include_overlay param
- `test_set_params_schema()` - Has all parameter options
- `test_add_tubercle_schema()` - Has x, y, radius params

---

## 4. Integration Tests (`tests/test_mcp_integration.py`)

End-to-end workflow tests with real images.

### Test Cases

- `test_full_extraction_workflow()` - Load → calibrate → extract → connect → save
- `test_manual_tubercle_workflow()` - Load → add manual tubercles → connect → stats
- `test_edit_after_extraction()` - Extract → delete some → add some → reconnect

---

## Fixtures (in conftest.py)

```python
@pytest.fixture
def flask_app():
    """Create Flask app with test config."""
    from fish_scale_ui.app import create_app
    app = create_app()
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(flask_app):
    """Flask test client."""
    return flask_app.test_client()

@pytest.fixture
def mcp_test_image(test_images_dir, tmp_path):
    """Copy a test image to temp location."""
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
        {'id': 1, 'centroid_x': 100, 'centroid_y': 100, 'radius_px': 10,
         'diameter_px': 20, 'diameter_um': 3.3, 'circularity': 0.95},
        {'id': 2, 'centroid_x': 150, 'centroid_y': 100, 'radius_px': 10,
         'diameter_px': 20, 'diameter_um': 3.3, 'circularity': 0.95},
        {'id': 3, 'centroid_x': 125, 'centroid_y': 150, 'radius_px': 10,
         'diameter_px': 20, 'diameter_um': 3.3, 'circularity': 0.95},
    ]

@pytest.fixture
def sample_calibration():
    """Sample calibration data."""
    return {'um_per_px': 0.165, 'method': 'manual'}
```

---

## Running Tests

```bash
# All MCP tests
uv run pytest tests/test_mcp*.py -v

# Specific test file
uv run pytest tests/test_mcp_api.py -v

# Single test
uv run pytest tests/test_mcp_api.py::TestTubercleEndpoints::test_tubercle_add_with_radius -v

# With coverage
uv run pytest tests/test_mcp*.py --cov=fish_scale_mcp --cov=fish_scale_ui.routes.mcp_api
```

---

## Acceptance Criteria

- [x] All Flask API endpoints return correct status codes
- [x] Screenshot rendering produces valid PNG images
- [x] Tubercle/connection CRUD operations maintain state correctly
- [x] Auto-connect produces valid graph structures
- [x] Statistics calculations match expected values
- [x] Error cases return appropriate error messages

## Test Results Summary

**Date:** 2025-12-18

| Test File | Tests | Passed | Status |
|-----------|-------|--------|--------|
| `test_mcp_api.py` | 42 | 42 | PASS |
| `test_mcp_screenshot.py` | 15 | 15 | PASS |
| `test_mcp_server.py` | 11 | 11 | PASS |
| **Total** | **68** | **68** | **100%** |

### Bug Fix During Testing

Fixed `mcp_api.py:auto_connect()` - was importing non-existent functions:
- Changed `extract_gabriel_edges` -> `filter_to_gabriel`
- Changed `extract_rng_edges` -> `filter_to_rng`
- Added proper Delaunay edge extraction before filtering
