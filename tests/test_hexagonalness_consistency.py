"""
Tests for hexagonalness calculation consistency.

Hexagonalness is calculated in two Python locations:
1. Python (core): fish_scale_analysis/core/measurement.py - calculate_hexagonalness()
   Used by CLI and core processing, works with Tubercle/NeighborEdge objects.
2. Python (MCP API): fish_scale_ui/routes/mcp_api.py - _calculate_hexagonalness_from_dicts()
   Single source of truth for web UI, works with dict representations.

JavaScript modules call the /api/hexagonalness endpoint which delegates to the MCP API
implementation, so there's no longer any JavaScript implementation to verify.

These tests ensure the two Python implementations produce consistent results.
"""

import pytest
import math
from typing import List, Dict, Any

from fish_scale_analysis.models import Tubercle, NeighborEdge, CalibrationData
from fish_scale_analysis.core.measurement import calculate_hexagonalness


# Import the MCP API's implementation
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from fish_scale_ui.routes.mcp_api import _calculate_hexagonalness_from_dicts


class TestHexagonalnessConsistency:
    """Test that all hexagonalness implementations produce consistent results."""

    @pytest.fixture
    def hexagonal_grid_data(self) -> Dict[str, Any]:
        """
        Create a simple hexagonal grid pattern for testing.

        Layout (7 nodes in hexagonal arrangement):
              1
            /   \\
           2     3
          / \\   / \\
         4   5-6   7

        This creates nodes with varying degrees (edge nodes have fewer connections).
        """
        # Create tubercles in a hex-like pattern
        # Row 0: node 0 at (50, 0)
        # Row 1: nodes 1,2 at (25, 43), (75, 43)
        # Row 2: nodes 3,4,5,6 at (0, 86), (50, 86), (100, 86), (150, 86)

        tubercle_positions = [
            (50, 0),      # 0 - top
            (25, 43),     # 1 - middle-left
            (75, 43),     # 2 - middle-right
            (0, 86),      # 3 - bottom-left
            (50, 86),     # 4 - bottom-center-left
            (100, 86),    # 5 - bottom-center-right
            (150, 86),    # 6 - bottom-right (extra node to test variation)
        ]

        # Create Tubercle objects (for core measurement.py)
        tubercles_objects = []
        for i, (x, y) in enumerate(tubercle_positions):
            tubercles_objects.append(Tubercle(
                id=i,
                centroid=(x, y),
                diameter_px=20.0,
                diameter_um=5.0,
                area_px=314.16,  # π * 10^2
                circularity=0.95,
            ))

        # Create dict representations (for MCP API and JavaScript)
        tubercles_dicts = []
        for i, (x, y) in enumerate(tubercle_positions):
            tubercles_dicts.append({
                'id': i,
                'centroid_x': x,
                'centroid_y': y,
                'diameter_px': 20.0,
                'diameter_um': 5.0,
                'circularity': 0.95,
            })

        # Define edges (connections between adjacent nodes)
        # Using consistent spacing for uniform edge distances
        edge_pairs = [
            (0, 1), (0, 2),           # from top
            (1, 2),                    # middle row
            (1, 3), (1, 4),           # from middle-left
            (2, 4), (2, 5),           # from middle-right
            (3, 4), (4, 5), (5, 6),   # bottom row
        ]

        calibration = CalibrationData(
            um_per_pixel=0.25,
            scale_bar_length_um=100,
            scale_bar_length_px=400,
            method='test'
        )

        # Create NeighborEdge objects
        edges_objects = []
        for a_id, b_id in edge_pairs:
            ta = tubercles_objects[a_id]
            tb = tubercles_objects[b_id]
            dx = ta.centroid[0] - tb.centroid[0]
            dy = ta.centroid[1] - tb.centroid[1]
            center_dist_px = math.sqrt(dx*dx + dy*dy)
            center_dist_um = center_dist_px * calibration.um_per_pixel
            edge_dist_px = center_dist_px - ta.radius_px - tb.radius_px
            edge_dist_um = edge_dist_px * calibration.um_per_pixel

            edges_objects.append(NeighborEdge(
                tubercle_a_id=a_id,
                tubercle_b_id=b_id,
                center_distance_px=center_dist_px,
                center_distance_um=center_dist_um,
                edge_distance_px=edge_dist_px,
                edge_distance_um=edge_dist_um,
            ))

        # Create edge dicts (using id1/id2 format as stored in extraction.py)
        edges_dicts = []
        for edge in edges_objects:
            ta = tubercles_objects[edge.tubercle_a_id]
            tb = tubercles_objects[edge.tubercle_b_id]
            edges_dicts.append({
                'id1': edge.tubercle_a_id,
                'id2': edge.tubercle_b_id,
                'x1': ta.centroid[0],
                'y1': ta.centroid[1],
                'x2': tb.centroid[0],
                'y2': tb.centroid[1],
                'center_distance_um': edge.center_distance_um,
                'edge_distance_um': edge.edge_distance_um,
            })

        return {
            'tubercles_objects': tubercles_objects,
            'tubercles_dicts': tubercles_dicts,
            'edges_objects': edges_objects,
            'edges_dicts': edges_dicts,
            'n_nodes': len(tubercle_positions),
            'n_edges': len(edge_pairs),
        }

    @pytest.fixture
    def uniform_grid_data(self) -> Dict[str, Any]:
        """
        Create a perfectly uniform square grid for testing edge cases.
        All edges have identical lengths.
        """
        # 3x3 grid with uniform spacing
        positions = []
        for row in range(3):
            for col in range(3):
                positions.append((col * 50, row * 50))

        tubercles_objects = []
        tubercles_dicts = []
        for i, (x, y) in enumerate(positions):
            tubercles_objects.append(Tubercle(
                id=i,
                centroid=(x, y),
                diameter_px=10.0,
                diameter_um=2.5,
                area_px=78.54,  # π * 5^2
                circularity=0.98,
            ))
            tubercles_dicts.append({
                'id': i,
                'centroid_x': x,
                'centroid_y': y,
                'diameter_px': 10.0,
                'diameter_um': 2.5,
                'circularity': 0.98,
            })

        # Connect adjacent nodes (horizontal and vertical only for uniformity)
        edge_pairs = [
            (0, 1), (1, 2),           # row 0
            (3, 4), (4, 5),           # row 1
            (6, 7), (7, 8),           # row 2
            (0, 3), (3, 6),           # col 0
            (1, 4), (4, 7),           # col 1
            (2, 5), (5, 8),           # col 2
        ]

        calibration = CalibrationData(um_per_pixel=0.25, scale_bar_length_um=100,
                                       scale_bar_length_px=400, method='test')

        edges_objects = []
        edges_dicts = []
        for a_id, b_id in edge_pairs:
            ta = tubercles_objects[a_id]
            tb = tubercles_objects[b_id]
            dx = ta.centroid[0] - tb.centroid[0]
            dy = ta.centroid[1] - tb.centroid[1]
            center_dist_px = math.sqrt(dx*dx + dy*dy)
            center_dist_um = center_dist_px * calibration.um_per_pixel
            edge_dist_um = (center_dist_px - ta.radius_px - tb.radius_px) * calibration.um_per_pixel

            edges_objects.append(NeighborEdge(
                tubercle_a_id=a_id, tubercle_b_id=b_id,
                center_distance_px=center_dist_px, center_distance_um=center_dist_um,
                edge_distance_px=center_dist_px - ta.radius_px - tb.radius_px,
                edge_distance_um=edge_dist_um,
            ))
            edges_dicts.append({
                'id1': a_id, 'id2': b_id,
                'x1': ta.centroid[0], 'y1': ta.centroid[1],
                'x2': tb.centroid[0], 'y2': tb.centroid[1],
                'center_distance_um': center_dist_um,
                'edge_distance_um': edge_dist_um,
            })

        return {
            'tubercles_objects': tubercles_objects,
            'tubercles_dicts': tubercles_dicts,
            'edges_objects': edges_objects,
            'edges_dicts': edges_dicts,
        }

    def test_python_implementations_agree(self, hexagonal_grid_data):
        """Test that core measurement.py and MCP API implementations agree."""
        # Calculate using core measurement.py (uses Tubercle/NeighborEdge objects)
        core_result = calculate_hexagonalness(
            hexagonal_grid_data['tubercles_objects'],
            hexagonal_grid_data['edges_objects'],
        )

        # Calculate using MCP API (uses dicts)
        mcp_result = _calculate_hexagonalness_from_dicts(
            hexagonal_grid_data['tubercles_dicts'],
            hexagonal_grid_data['edges_dicts'],
        )

        # Compare all fields
        assert core_result['n_nodes'] == mcp_result['n_nodes'], \
            f"n_nodes mismatch: core={core_result['n_nodes']}, mcp={mcp_result['n_nodes']}"

        assert core_result['reliability'] == mcp_result['reliability'], \
            f"reliability mismatch: core={core_result['reliability']}, mcp={mcp_result['reliability']}"

        # Numeric fields should be very close (allow small floating point differences)
        numeric_fields = [
            'hexagonalness_score',
            'spacing_uniformity',
            'degree_score',
            'edge_ratio_score',
            'mean_degree',
            'spacing_cv',
        ]

        for field in numeric_fields:
            core_val = core_result[field]
            mcp_val = mcp_result[field]
            assert abs(core_val - mcp_val) < 0.001, \
                f"{field} mismatch: core={core_val:.6f}, mcp={mcp_val:.6f}"

    def test_python_implementations_agree_uniform_grid(self, uniform_grid_data):
        """Test implementations agree on uniform grid (edge case with CV=0)."""
        core_result = calculate_hexagonalness(
            uniform_grid_data['tubercles_objects'],
            uniform_grid_data['edges_objects'],
        )

        mcp_result = _calculate_hexagonalness_from_dicts(
            uniform_grid_data['tubercles_dicts'],
            uniform_grid_data['edges_dicts'],
        )

        numeric_fields = [
            'hexagonalness_score', 'spacing_uniformity', 'degree_score',
            'edge_ratio_score', 'mean_degree', 'spacing_cv',
        ]

        for field in numeric_fields:
            core_val = core_result[field]
            mcp_val = mcp_result[field]
            assert abs(core_val - mcp_val) < 0.001, \
                f"{field} mismatch on uniform grid: core={core_val:.6f}, mcp={mcp_val:.6f}"

    def test_empty_data_handling(self):
        """Test that all implementations handle empty data consistently."""
        core_result = calculate_hexagonalness([], [])
        mcp_result = _calculate_hexagonalness_from_dicts([], [])

        assert core_result['hexagonalness_score'] == 0.0
        assert mcp_result['hexagonalness_score'] == 0.0
        assert core_result['reliability'] == 'none'
        assert mcp_result['reliability'] == 'none'

    def test_few_nodes_handling(self):
        """Test that implementations handle <4 nodes consistently."""
        # 3 nodes (below minimum)
        tubercles_obj = [
            Tubercle(id=i, centroid=(i*50, 0), diameter_px=10, diameter_um=2.5,
                    area_px=78.54, circularity=0.9)
            for i in range(3)
        ]
        tubercles_dict = [
            {'id': i, 'centroid_x': i*50, 'centroid_y': 0, 'diameter_um': 2.5}
            for i in range(3)
        ]

        edges_obj = [
            NeighborEdge(tubercle_a_id=0, tubercle_b_id=1,
                        center_distance_px=50, center_distance_um=12.5,
                        edge_distance_px=40, edge_distance_um=10),
        ]
        edges_dict = [
            {'id1': 0, 'id2': 1, 'center_distance_um': 12.5, 'edge_distance_um': 10},
        ]

        core_result = calculate_hexagonalness(tubercles_obj, edges_obj)
        mcp_result = _calculate_hexagonalness_from_dicts(tubercles_dict, edges_dict)

        assert core_result['hexagonalness_score'] == 0.0
        assert mcp_result['hexagonalness_score'] == 0.0
        assert core_result['reliability'] == 'none'
        assert mcp_result['reliability'] == 'none'

    def test_degree_score_calculation(self, hexagonal_grid_data):
        """Test that degree_score is calculated consistently."""
        core_result = calculate_hexagonalness(
            hexagonal_grid_data['tubercles_objects'],
            hexagonal_grid_data['edges_objects'],
        )
        mcp_result = _calculate_hexagonalness_from_dicts(
            hexagonal_grid_data['tubercles_dicts'],
            hexagonal_grid_data['edges_dicts'],
        )

        # Both should have the same degree histogram
        core_histogram = core_result.get('degree_histogram', {})
        mcp_histogram = mcp_result.get('degree_histogram', {})

        assert core_histogram == mcp_histogram, \
            f"Degree histograms differ: core={core_histogram}, mcp={mcp_histogram}"

        # Degree scores should match
        assert abs(core_result['degree_score'] - mcp_result['degree_score']) < 0.001

    def test_edge_id_formats(self):
        """Test that MCP API handles both edge ID formats correctly."""
        tubercles = [
            {'id': i, 'centroid_x': i*50, 'centroid_y': 0, 'diameter_um': 2.5}
            for i in range(5)
        ]

        # Format 1: id1/id2 (as stored by extraction.py)
        edges_id1_id2 = [
            {'id1': 0, 'id2': 1, 'edge_distance_um': 10},
            {'id1': 1, 'id2': 2, 'edge_distance_um': 10},
            {'id1': 2, 'id2': 3, 'edge_distance_um': 10},
            {'id1': 3, 'id2': 4, 'edge_distance_um': 10},
        ]

        # Format 2: tubercle_a_id/tubercle_b_id (as in NeighborEdge)
        edges_tubercle_ids = [
            {'tubercle_a_id': 0, 'tubercle_b_id': 1, 'edge_distance_um': 10},
            {'tubercle_a_id': 1, 'tubercle_b_id': 2, 'edge_distance_um': 10},
            {'tubercle_a_id': 2, 'tubercle_b_id': 3, 'edge_distance_um': 10},
            {'tubercle_a_id': 3, 'tubercle_b_id': 4, 'edge_distance_um': 10},
        ]

        result1 = _calculate_hexagonalness_from_dicts(tubercles, edges_id1_id2)
        result2 = _calculate_hexagonalness_from_dicts(tubercles, edges_tubercle_ids)

        # Results should be identical regardless of ID format
        assert abs(result1['hexagonalness_score'] - result2['hexagonalness_score']) < 0.001
        assert abs(result1['degree_score'] - result2['degree_score']) < 0.001
        assert abs(result1['mean_degree'] - result2['mean_degree']) < 0.001

    def test_formula_weights(self, hexagonal_grid_data):
        """Test that the hexagonalness formula uses correct weights."""
        result = calculate_hexagonalness(
            hexagonal_grid_data['tubercles_objects'],
            hexagonal_grid_data['edges_objects'],
        )

        # Formula: hex = 0.40 * spacing_uniformity + 0.45 * degree_score + 0.15 * edge_ratio_score
        expected_score = (
            0.40 * result['spacing_uniformity'] +
            0.45 * result['degree_score'] +
            0.15 * result['edge_ratio_score']
        )

        assert abs(result['hexagonalness_score'] - expected_score) < 0.0001, \
            f"Formula mismatch: calculated={result['hexagonalness_score']:.6f}, expected={expected_score:.6f}"

    def test_spacing_uniformity_from_cv(self, uniform_grid_data):
        """Test that spacing_uniformity is correctly derived from CV."""
        result = calculate_hexagonalness(
            uniform_grid_data['tubercles_objects'],
            uniform_grid_data['edges_objects'],
        )

        # Formula: spacing_uniformity = max(0, 1 - 2 * cv)
        expected_uniformity = max(0, 1 - 2 * result['spacing_cv'])

        assert abs(result['spacing_uniformity'] - expected_uniformity) < 0.0001, \
            f"Spacing uniformity formula mismatch: got={result['spacing_uniformity']:.6f}, expected={expected_uniformity:.6f}"

    def test_edge_ratio_score_calculation(self, hexagonal_grid_data):
        """Test edge_ratio_score formula: max(0, 1 - |ratio - 3.0| / 2).

        The edge ratio uses interior nodes only (not boundary nodes) and
        ideal ratio of 3.0 (for hexagonal lattice).
        """
        result = calculate_hexagonalness(
            hexagonal_grid_data['tubercles_objects'],
            hexagonal_grid_data['edges_objects'],
        )

        # Use interior node count (n_interior_nodes), not total nodes
        n_interior = result['n_interior_nodes']
        n_edges = hexagonal_grid_data['n_edges']

        if n_interior > 0:
            ratio = n_edges / n_interior
            expected_score = max(0, 1 - abs(ratio - 3.0) / 2)
        else:
            expected_score = 0.0

        assert abs(result['edge_ratio_score'] - expected_score) < 0.0001, \
            f"Edge ratio score mismatch: got={result['edge_ratio_score']:.6f}, expected={expected_score:.6f}"


class TestHexagonalnessReliability:
    """Test reliability indicator across implementations."""

    def test_high_reliability_threshold(self):
        """Test that 15+ nodes gives 'high' reliability."""
        tubercles_obj = [
            Tubercle(id=i, centroid=(i*20, 0), diameter_px=10, diameter_um=2.5,
                    area_px=78.54, circularity=0.9)
            for i in range(15)
        ]
        tubercles_dict = [
            {'id': i, 'centroid_x': i*20, 'centroid_y': 0, 'diameter_um': 2.5}
            for i in range(15)
        ]

        edges_obj = [
            NeighborEdge(tubercle_a_id=i, tubercle_b_id=i+1,
                        center_distance_px=20, center_distance_um=5,
                        edge_distance_px=10, edge_distance_um=2.5)
            for i in range(14)
        ]
        edges_dict = [
            {'id1': i, 'id2': i+1, 'edge_distance_um': 2.5}
            for i in range(14)
        ]

        core_result = calculate_hexagonalness(tubercles_obj, edges_obj)
        mcp_result = _calculate_hexagonalness_from_dicts(tubercles_dict, edges_dict)

        assert core_result['reliability'] == 'high'
        assert mcp_result['reliability'] == 'high'

    def test_low_reliability_threshold(self):
        """Test that 4-14 nodes gives 'low' reliability."""
        for n_nodes in [4, 10, 14]:
            tubercles_obj = [
                Tubercle(id=i, centroid=(i*20, 0), diameter_px=10, diameter_um=2.5,
                        area_px=78.54, circularity=0.9)
                for i in range(n_nodes)
            ]
            tubercles_dict = [
                {'id': i, 'centroid_x': i*20, 'centroid_y': 0, 'diameter_um': 2.5}
                for i in range(n_nodes)
            ]

            edges_obj = [
                NeighborEdge(tubercle_a_id=i, tubercle_b_id=i+1,
                            center_distance_px=20, center_distance_um=5,
                            edge_distance_px=10, edge_distance_um=2.5)
                for i in range(n_nodes - 1)
            ]
            edges_dict = [
                {'id1': i, 'id2': i+1, 'edge_distance_um': 2.5}
                for i in range(n_nodes - 1)
            ]

            core_result = calculate_hexagonalness(tubercles_obj, edges_obj)
            mcp_result = _calculate_hexagonalness_from_dicts(tubercles_dict, edges_dict)

            assert core_result['reliability'] == 'low', f"Expected 'low' for {n_nodes} nodes"
            assert mcp_result['reliability'] == 'low', f"Expected 'low' for {n_nodes} nodes"


class TestDegreeScoreWeighting:
    """Test the degree score weighting system."""

    def _create_nodes_with_degree(self, degree: int, n_nodes: int = 10):
        """Helper to create nodes with a specific degree."""
        tubercles = [
            {'id': i, 'centroid_x': i*50, 'centroid_y': 0, 'diameter_um': 2.5}
            for i in range(n_nodes)
        ]

        # Create edges to give each interior node the specified degree
        # For simplicity, connect node 0 to nodes 1..degree
        edges = []
        for target in range(1, min(degree + 1, n_nodes)):
            edges.append({'id1': 0, 'id2': target, 'edge_distance_um': 10})

        return tubercles, edges

    def test_degree_5_6_7_gets_weight_1(self):
        """Nodes with degree 5, 6, or 7 should get weight 1.0."""
        for degree in [5, 6, 7]:
            tubercles, edges = self._create_nodes_with_degree(degree, n_nodes=10)
            result = _calculate_hexagonalness_from_dicts(tubercles, edges)
            # Node 0 has `degree` connections, check it's counted correctly
            histogram = result.get('degree_histogram', {})
            assert degree in histogram or str(degree) in histogram, \
                f"Expected degree {degree} in histogram: {histogram}"

    def test_degree_4_8_gets_weight_07(self):
        """Nodes with degree 4 or 8 should get weight 0.7."""
        for degree in [4, 8]:
            tubercles, edges = self._create_nodes_with_degree(degree, n_nodes=10)
            result = _calculate_hexagonalness_from_dicts(tubercles, edges)
            histogram = result.get('degree_histogram', {})
            assert degree in histogram or str(degree) in histogram, \
                f"Expected degree {degree} in histogram: {histogram}"

    def test_degree_3_9_gets_weight_03(self):
        """Nodes with degree 3 or 9 should get weight 0.3."""
        for degree in [3, 9]:
            tubercles, edges = self._create_nodes_with_degree(degree, n_nodes=12)
            result = _calculate_hexagonalness_from_dicts(tubercles, edges)
            histogram = result.get('degree_histogram', {})
            assert degree in histogram or str(degree) in histogram, \
                f"Expected degree {degree} in histogram: {histogram}"


class TestNegativeEdgeDistances:
    """Test handling of negative edge distances (overlapping tubercles)."""

    def test_negative_distances_filtered(self):
        """Negative edge_distance_um values should be filtered from spacing calculation."""
        tubercles = [
            {'id': i, 'centroid_x': i*50, 'centroid_y': 0, 'diameter_um': 2.5}
            for i in range(5)
        ]

        edges = [
            {'id1': 0, 'id2': 1, 'edge_distance_um': 10},   # positive
            {'id1': 1, 'id2': 2, 'edge_distance_um': -5},   # negative (overlapping)
            {'id1': 2, 'id2': 3, 'edge_distance_um': 10},   # positive
            {'id1': 3, 'id2': 4, 'edge_distance_um': 10},   # positive
        ]

        result = _calculate_hexagonalness_from_dicts(tubercles, edges)

        # Spacing CV should be calculated only from positive values
        # All positive values are 10, so CV should be 0 (perfect uniformity)
        assert result['spacing_cv'] == 0.0, \
            f"Expected CV=0 for uniform positive spacings, got {result['spacing_cv']}"
        assert result['spacing_uniformity'] == 1.0, \
            f"Expected uniformity=1 for CV=0, got {result['spacing_uniformity']}"
