"""Tests for measurement module."""

import numpy as np
import pytest
from fish_scale_analysis.core.calibration import calibrate_manual
from fish_scale_analysis.core.measurement import (
    build_neighbor_graph,
    get_neighbor_edges,
    measure_diameters,
    measure_intertubercular_spaces,
    classify_genus,
    measure_metrics,
    calculate_hexagonalness,
)
from fish_scale_analysis.models import Tubercle, NeighborEdge


@pytest.fixture
def simple_calibration():
    """Create a 1:1 calibration for testing."""
    return calibrate_manual(scale_bar_um=100.0, scale_bar_px=100.0)


@pytest.fixture
def sample_tubercles():
    """Create a list of sample tubercles for testing."""
    # Create tubercles in a grid pattern
    tubercles = []
    id_counter = 1

    for row in range(3):
        for col in range(3):
            t = Tubercle(
                id=id_counter,
                centroid=(col * 50 + 50, row * 50 + 50),  # (x, y)
                diameter_px=20.0,
                diameter_um=4.0,
                area_px=314.0,
                circularity=0.9,
            )
            tubercles.append(t)
            id_counter += 1

    return tubercles


class TestNeighborGraph:
    """Tests for neighbor graph construction."""

    def test_build_triangulation(self, sample_tubercles):
        """Test building Delaunay triangulation."""
        tri = build_neighbor_graph(sample_tubercles)

        assert tri is not None
        assert len(tri.simplices) > 0

    def test_too_few_tubercles(self):
        """Test that < 4 tubercles returns None."""
        few = [
            Tubercle(1, (0, 0), 10, 2, 78, 0.9),
            Tubercle(2, (50, 0), 10, 2, 78, 0.9),
            Tubercle(3, (25, 50), 10, 2, 78, 0.9),
        ]

        tri = build_neighbor_graph(few)
        assert tri is None

    def test_empty_list(self):
        """Test empty tubercle list."""
        tri = build_neighbor_graph([])
        assert tri is None


class TestNeighborEdges:
    """Tests for neighbor edge extraction."""

    def test_edge_extraction(self, sample_tubercles, simple_calibration):
        """Test extracting edges from triangulation."""
        tri = build_neighbor_graph(sample_tubercles)
        edges = get_neighbor_edges(sample_tubercles, tri, simple_calibration)

        assert len(edges) > 0

        for edge in edges:
            assert edge.tubercle_a_id > 0
            assert edge.tubercle_b_id > 0
            assert edge.center_distance_px > 0
            assert edge.center_distance_um > 0

    def test_edge_distance_calculation(self, simple_calibration):
        """Test that edge distances are calculated correctly."""
        # Two tubercles 100 pixels apart, each with radius 10 pixels
        tubercles = [
            Tubercle(1, (0, 0), 20, 20, 314, 0.9),    # Diameter 20
            Tubercle(2, (100, 0), 20, 20, 314, 0.9),  # 100 pixels to the right
        ]

        tri = build_neighbor_graph(tubercles + [
            Tubercle(3, (50, 50), 20, 20, 314, 0.9),  # Need 4 points for triangulation
            Tubercle(4, (50, -50), 20, 20, 314, 0.9),
        ])

        edges = get_neighbor_edges(tubercles + [
            Tubercle(3, (50, 50), 20, 20, 314, 0.9),
            Tubercle(4, (50, -50), 20, 20, 314, 0.9),
        ], tri, simple_calibration)

        # Find edge between tubercles 1 and 2
        edge_1_2 = None
        for e in edges:
            if {e.tubercle_a_id, e.tubercle_b_id} == {1, 2}:
                edge_1_2 = e
                break

        if edge_1_2:
            # Center distance should be 100
            assert abs(edge_1_2.center_distance_px - 100) < 1
            # Edge distance should be 100 - 10 - 10 = 80
            assert abs(edge_1_2.edge_distance_px - 80) < 1


class TestDiameterMeasurement:
    """Tests for diameter measurement."""

    def test_measure_diameters(self, sample_tubercles):
        """Test diameter statistics calculation."""
        diameters, mean, std = measure_diameters(sample_tubercles)

        assert len(diameters) == len(sample_tubercles)
        assert mean == 4.0  # All tubercles have diameter_um = 4.0
        assert std == 0.0   # All same size

    def test_empty_list(self):
        """Test empty tubercle list."""
        diameters, mean, std = measure_diameters([])

        assert len(diameters) == 0
        assert mean == 0.0
        assert std == 0.0


class TestSpacingMeasurement:
    """Tests for intertubercular space measurement."""

    def test_positive_spacing_filter(self):
        """Test that only positive spacings are included."""
        from fish_scale_analysis.models import NeighborEdge

        edges = [
            NeighborEdge(1, 2, 100, 100, 80, 80),    # Positive
            NeighborEdge(2, 3, 50, 50, -5, -5),      # Negative (overlapping)
            NeighborEdge(3, 4, 100, 100, 60, 60),    # Positive
        ]

        spaces, mean, std = measure_intertubercular_spaces(edges)

        assert len(spaces) == 2  # Only 2 positive
        assert mean == 70.0      # (80 + 60) / 2

    def test_empty_list(self):
        """Test empty edge list."""
        spaces, mean, std = measure_intertubercular_spaces([])

        assert len(spaces) == 0
        assert mean == 0.0


class TestGenusClassification:
    """Tests for genus classification."""

    def test_lepisosteus_classification(self):
        """Test classification within Lepisosteus range."""
        genus, confidence = classify_genus(4.0, 3.5)

        assert genus == "Lepisosteus"
        assert confidence == "high"

    def test_atractosteus_classification(self):
        """Test classification within Atractosteus range."""
        genus, confidence = classify_genus(7.0, 2.5)

        assert genus == "Atractosteus"
        assert confidence == "high"

    def test_polypterus_classification(self):
        """Test classification within Polypterus range."""
        genus, confidence = classify_genus(2.5, 6.5)

        assert genus == "Polypterus"
        assert confidence == "high"

    def test_borderline_classification(self):
        """Test borderline values get lower confidence."""
        # Values outside all ranges but close
        genus, confidence = classify_genus(5.5, 5.0)

        assert confidence in ["medium", "low"]

    def test_unknown_classification(self):
        """Test very unusual values."""
        genus, confidence = classify_genus(20.0, 20.0)

        assert genus == "Unknown" or confidence in ["low", "none"]


class TestMeasureMetrics:
    """Tests for complete metrics measurement."""

    def test_measure_metrics(self, sample_tubercles, simple_calibration):
        """Test complete metrics measurement."""
        result = measure_metrics(sample_tubercles, simple_calibration, "test.tif")

        assert result.n_tubercles == len(sample_tubercles)
        assert len(result.tubercle_diameters_um) == len(sample_tubercles)
        assert result.mean_diameter_um > 0
        assert result.suggested_genus is not None

    def test_empty_tubercles(self, simple_calibration):
        """Test with no tubercles."""
        result = measure_metrics([], simple_calibration, "empty.tif")

        assert result.n_tubercles == 0
        assert result.mean_diameter_um == 0
        assert result.mean_space_um == 0
        assert result.suggested_genus == "Unknown"

    def test_summary_dict(self, sample_tubercles, simple_calibration):
        """Test summary dictionary generation."""
        result = measure_metrics(sample_tubercles, simple_calibration, "test.tif")
        summary = result.summary_dict()

        assert "image" in summary
        assert "n_tubercles" in summary
        assert "mean_diameter_um" in summary
        assert "mean_space_um" in summary
        assert "suggested_genus" in summary


class TestHexagonalness:
    """Tests for hexagonalness calculation."""

    def test_hexagonalness_with_edges(self, sample_tubercles, simple_calibration):
        """Test hexagonalness calculation with edges."""
        # Build neighbor graph
        tri = build_neighbor_graph(sample_tubercles)
        edges = get_neighbor_edges(sample_tubercles, tri, simple_calibration)

        result = calculate_hexagonalness(sample_tubercles, edges)

        assert 'hexagonalness_score' in result
        assert 'spacing_uniformity' in result
        assert 'degree_score' in result
        assert 'mean_degree' in result
        assert 'spacing_cv' in result
        assert 'degree_histogram' in result

        # Score should be between 0 and 1
        assert 0 <= result['hexagonalness_score'] <= 1
        assert 0 <= result['spacing_uniformity'] <= 1
        assert 0 <= result['degree_score'] <= 1

    def test_hexagonalness_empty_tubercles(self):
        """Test hexagonalness with no tubercles."""
        result = calculate_hexagonalness([], [])

        assert result['hexagonalness_score'] == 0.0
        assert result['mean_degree'] == 0.0

    def test_hexagonalness_few_tubercles(self):
        """Test hexagonalness with fewer than 4 tubercles."""
        few = [
            Tubercle(1, (0, 0), 10, 2, 78, 0.9),
            Tubercle(2, (50, 0), 10, 2, 78, 0.9),
            Tubercle(3, (25, 43), 10, 2, 78, 0.9),
        ]
        result = calculate_hexagonalness(few, [])

        assert result['hexagonalness_score'] == 0.0

    def test_hexagonalness_uniform_grid(self, sample_tubercles, simple_calibration):
        """Test that a uniform grid scores well on spacing uniformity."""
        # The sample_tubercles fixture creates a regular 3x3 grid
        tri = build_neighbor_graph(sample_tubercles)
        edges = get_neighbor_edges(sample_tubercles, tri, simple_calibration)

        result = calculate_hexagonalness(sample_tubercles, edges)

        # A regular grid should have good spacing uniformity
        # CV should be low for uniform spacing
        assert result['spacing_cv'] < 0.5

    def test_hexagonalness_reliability_indicator(self, simple_calibration):
        """Test reliability indicator for different node counts."""
        # 4 nodes - low reliability
        t4 = [
            Tubercle(1, (0, 0), 10, 2, 78, 0.9),
            Tubercle(2, (50, 0), 10, 2, 78, 0.9),
            Tubercle(3, (25, 43), 10, 2, 78, 0.9),
            Tubercle(4, (25, 15), 10, 2, 78, 0.9),
        ]
        tri = build_neighbor_graph(t4)
        edges = get_neighbor_edges(t4, tri, simple_calibration)
        result = calculate_hexagonalness(t4, edges)

        assert result['reliability'] == 'low'
        assert result['n_nodes'] == 4

        # 20 nodes - high reliability
        import math
        t20 = []
        for row in range(5):
            for col in range(4):
                x = col * 30 + (15 if row % 2 else 0)
                y = row * 26
                t20.append(Tubercle(len(t20)+1, (x, y), 10, 2, 78, 0.9))

        tri = build_neighbor_graph(t20)
        edges = get_neighbor_edges(t20, tri, simple_calibration)
        result = calculate_hexagonalness(t20, edges)

        assert result['reliability'] == 'high'
        assert result['n_nodes'] == 20

    def test_hexagonalness_none_reliability(self):
        """Test that 0-3 nodes returns none reliability."""
        t3 = [
            Tubercle(1, (0, 0), 10, 2, 78, 0.9),
            Tubercle(2, (50, 0), 10, 2, 78, 0.9),
            Tubercle(3, (25, 43), 10, 2, 78, 0.9),
        ]
        result = calculate_hexagonalness(t3, [])

        assert result['reliability'] == 'none'
        assert result['n_nodes'] == 0
