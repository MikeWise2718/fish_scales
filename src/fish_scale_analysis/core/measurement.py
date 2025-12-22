"""Measurement of tubercle metrics and genus classification."""

from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from scipy.spatial import Delaunay

from ..models import (
    CalibrationData,
    MeasurementResult,
    NeighborEdge,
    Tubercle,
    GENUS_REFERENCE_RANGES,
)
from .calibration import calibrate_manual, estimate_calibration_700x
from .preprocessing import load_image, preprocess_pipeline
from .detection import detect_tubercles


def build_neighbor_graph(tubercles: List[Tubercle]) -> Optional[Delaunay]:
    """
    Build a Delaunay triangulation to identify natural neighbors.

    Args:
        tubercles: List of detected tubercles

    Returns:
        Delaunay triangulation object, or None if < 4 tubercles
    """
    if len(tubercles) < 4:
        return None

    # Extract centroids
    points = np.array([t.centroid for t in tubercles])

    # Build triangulation
    tri = Delaunay(points)
    return tri


def filter_to_rng(
    points: np.ndarray,
    delaunay_edges: set,
) -> set:
    """
    Filter Delaunay edges to Relative Neighborhood Graph (RNG).

    An edge (a, b) is in the RNG if and only if there is no point c
    such that:
        max(dist(a,c), dist(b,c)) < dist(a,b)

    In other words, keep edge (a,b) only if no other point is closer
    to BOTH a and b than they are to each other.

    Args:
        points: Array of shape (n, 2) with point coordinates
        delaunay_edges: Set of (i, j) tuples representing Delaunay edges

    Returns:
        Set of (i, j) tuples representing RNG edges
    """
    n = len(points)
    rng_edges = set()

    for edge in delaunay_edges:
        i, j = edge
        pi, pj = points[i], points[j]
        dist_ij = np.linalg.norm(pi - pj)

        # Check if any other point violates the RNG condition
        is_rng_edge = True
        for k in range(n):
            if k == i or k == j:
                continue

            pk = points[k]
            dist_ik = np.linalg.norm(pi - pk)
            dist_jk = np.linalg.norm(pj - pk)

            # If point k is closer to both i and j than they are to each other,
            # then edge (i,j) is not in the RNG
            if max(dist_ik, dist_jk) < dist_ij:
                is_rng_edge = False
                break

        if is_rng_edge:
            rng_edges.add(edge)

    return rng_edges


def filter_to_gabriel(
    points: np.ndarray,
    delaunay_edges: set,
) -> set:
    """
    Filter Delaunay edges to Gabriel Graph.

    An edge (a, b) is in the Gabriel Graph if and only if no other point
    lies inside the circle with diameter ab.

    Gabriel Graph is a superset of RNG (contains more edges).

    Args:
        points: Array of shape (n, 2) with point coordinates
        delaunay_edges: Set of (i, j) tuples representing Delaunay edges

    Returns:
        Set of (i, j) tuples representing Gabriel edges
    """
    n = len(points)
    gabriel_edges = set()

    for edge in delaunay_edges:
        i, j = edge
        pi, pj = points[i], points[j]

        # Circle center is midpoint, radius is half the distance
        center = (pi + pj) / 2
        radius_sq = np.sum((pi - pj) ** 2) / 4

        # Check if any other point lies inside this circle
        is_gabriel_edge = True
        for k in range(n):
            if k == i or k == j:
                continue

            pk = points[k]
            dist_sq = np.sum((pk - center) ** 2)

            if dist_sq < radius_sq:
                is_gabriel_edge = False
                break

        if is_gabriel_edge:
            gabriel_edges.add(edge)

    return gabriel_edges


def get_neighbor_edges(
    tubercles: List[Tubercle],
    triangulation: Delaunay,
    calibration: CalibrationData,
    graph_type: str = "delaunay",
    max_distance_factor: Optional[float] = None,
) -> List[NeighborEdge]:
    """
    Extract neighbor edges from triangulation with optional filtering.

    Args:
        tubercles: List of tubercles
        triangulation: Delaunay triangulation
        calibration: Calibration data
        graph_type: Type of neighbor graph to use:
            - "delaunay": Full Delaunay triangulation (default, may have long edges)
            - "gabriel": Gabriel graph (removes edges with points inside diameter circle)
            - "rng": Relative Neighborhood Graph (most conservative, natural neighbors only)
        max_distance_factor: If set, filter out edges longer than this factor times
            the median edge length. E.g., 1.5 removes edges > 1.5× median.

    Returns:
        List of NeighborEdge objects
    """
    # Get all unique edges from triangulation
    all_edges = set()
    for simplex in triangulation.simplices:
        for i in range(3):
            for j in range(i + 1, 3):
                edge = tuple(sorted([simplex[i], simplex[j]]))
                all_edges.add(edge)

    # Get points array
    points = np.array([t.centroid for t in tubercles])

    # Filter edges based on graph type
    if graph_type == "rng":
        filtered_edges = filter_to_rng(points, all_edges)
    elif graph_type == "gabriel":
        filtered_edges = filter_to_gabriel(points, all_edges)
    else:  # delaunay
        filtered_edges = all_edges

    # Calculate distances for all filtered edges
    edge_data = []
    for idx_a, idx_b in filtered_edges:
        tubercle_a = tubercles[idx_a]
        tubercle_b = tubercles[idx_b]

        # Calculate center-to-center distance
        dx = tubercle_a.centroid[0] - tubercle_b.centroid[0]
        dy = tubercle_a.centroid[1] - tubercle_b.centroid[1]
        center_distance_px = np.sqrt(dx**2 + dy**2)
        center_distance_um = center_distance_px * calibration.um_per_pixel

        # Calculate edge-to-edge distance (intertubercular space)
        edge_distance_px = (
            center_distance_px
            - tubercle_a.radius_px
            - tubercle_b.radius_px
        )
        edge_distance_um = edge_distance_px * calibration.um_per_pixel

        edge_data.append({
            'tubercle_a': tubercle_a,
            'tubercle_b': tubercle_b,
            'center_distance_px': center_distance_px,
            'center_distance_um': center_distance_um,
            'edge_distance_px': edge_distance_px,
            'edge_distance_um': edge_distance_um,
        })

    # Apply max distance filter based on median
    if max_distance_factor is not None and edge_data:
        distances = [e['center_distance_px'] for e in edge_data]
        median_dist = np.median(distances)
        max_dist = median_dist * max_distance_factor
        edge_data = [e for e in edge_data if e['center_distance_px'] <= max_dist]

    # Convert to NeighborEdge objects
    edges = []
    for e in edge_data:
        edge = NeighborEdge(
            tubercle_a_id=e['tubercle_a'].id,
            tubercle_b_id=e['tubercle_b'].id,
            center_distance_px=float(e['center_distance_px']),
            center_distance_um=float(e['center_distance_um']),
            edge_distance_px=float(e['edge_distance_px']),
            edge_distance_um=float(e['edge_distance_um']),
        )
        edges.append(edge)

    return edges


def measure_diameters(tubercles: List[Tubercle]) -> Tuple[List[float], float, float]:
    """
    Calculate diameter statistics.

    Args:
        tubercles: List of tubercles

    Returns:
        Tuple of (list of diameters, mean, std)
    """
    if not tubercles:
        return [], 0.0, 0.0

    diameters = [t.diameter_um for t in tubercles]
    mean_diam = float(np.mean(diameters))
    std_diam = float(np.std(diameters))

    return diameters, mean_diam, std_diam


def measure_intertubercular_spaces(
    edges: List[NeighborEdge],
    min_space_um: float = 0.5,
) -> Tuple[List[float], float, float]:
    """
    Calculate intertubercular space statistics.

    Only includes positive (non-overlapping) distances.

    Args:
        edges: List of neighbor edges
        min_space_um: Minimum space to include (filters noise)

    Returns:
        Tuple of (list of spaces, mean, std)
    """
    if not edges:
        return [], 0.0, 0.0

    # Filter to positive distances above threshold
    spaces = [e.edge_distance_um for e in edges if e.edge_distance_um >= min_space_um]

    if not spaces:
        return [], 0.0, 0.0

    mean_space = float(np.mean(spaces))
    std_space = float(np.std(spaces))

    return spaces, mean_space, std_space


def measure_nearest_neighbor_spacing(
    tubercles: List[Tubercle],
    calibration: CalibrationData,
    min_space_um: float = 0.0,
) -> Tuple[List[float], float, float]:
    """
    Calculate intertubercular space using nearest-neighbor distances.

    This matches the methodology used in Gayet & Meunier papers, where
    spacing is measured between immediately adjacent tubercles only.

    Args:
        tubercles: List of detected tubercles
        calibration: Calibration data for unit conversion
        min_space_um: Minimum space to include (filters overlapping tubercles)

    Returns:
        Tuple of (list of spaces, mean, std)
    """
    if len(tubercles) < 2:
        return [], 0.0, 0.0

    from scipy.spatial import cKDTree

    # Get positions and radii
    positions = np.array([t.centroid for t in tubercles])
    radii_um = np.array([t.radius_px * calibration.um_per_pixel for t in tubercles])

    # Build KD-tree for nearest neighbor queries
    tree = cKDTree(positions)

    # Find nearest neighbor for each tubercle
    distances_px, indices = tree.query(positions, k=2)  # k=2 because first is self
    nn_indices = indices[:, 1]
    nn_dists_px = distances_px[:, 1]
    nn_center_dists_um = nn_dists_px * calibration.um_per_pixel

    # Calculate edge-to-edge distance for each nearest neighbor pair
    spaces = []
    for i in range(len(tubercles)):
        j = nn_indices[i]
        edge_dist = nn_center_dists_um[i] - radii_um[i] - radii_um[j]
        if edge_dist >= min_space_um:
            spaces.append(float(edge_dist))

    if not spaces:
        return [], 0.0, 0.0

    mean_space = float(np.mean(spaces))
    std_space = float(np.std(spaces))

    return spaces, mean_space, std_space


def calculate_hexagonalness(
    tubercles: List[Tubercle],
    edges: List[NeighborEdge],
    min_nodes_for_reliable: int = 15,
) -> dict:
    """
    Calculate hexagonalness metrics for the detected pattern.

    A perfect hexagonal lattice has:
    - Uniform spacing (low coefficient of variation)
    - Each interior node has 6 neighbors (edge nodes have fewer)
    - Edge count ≈ 3 × node count
    - Angles between edges are multiples of 60°

    Args:
        tubercles: List of detected tubercles
        edges: List of neighbor edges
        min_nodes_for_reliable: Minimum nodes for statistically reliable metrics

    Returns:
        Dictionary with hexagonalness metrics:
        - hexagonalness_score: Overall score 0-1 (1 = perfect hex)
        - spacing_uniformity: How uniform edge lengths are (0-1)
        - degree_score: Fraction of nodes with appropriate neighbor count (0-1)
        - edge_ratio_score: How close edge/node ratio is to 3 (0-1)
        - mean_degree: Average number of neighbors per node
        - degree_histogram: Count of nodes by neighbor count
        - spacing_cv: Coefficient of variation of edge lengths
        - reliability: 'high' (≥15 nodes), 'low' (4-14 nodes), 'none' (<4 nodes)
        - n_nodes: Number of nodes used in calculation
    """
    from collections import defaultdict

    result = {
        'hexagonalness_score': 0.0,
        'spacing_uniformity': 0.0,
        'degree_score': 0.0,
        'edge_ratio_score': 0.0,
        'mean_degree': 0.0,
        'degree_histogram': {},
        'spacing_cv': 1.0,
        'reliability': 'none',
        'n_nodes': 0,
    }

    if not tubercles or len(tubercles) < 4:
        return result

    n_nodes = len(tubercles)
    result['n_nodes'] = n_nodes
    result['reliability'] = 'high' if n_nodes >= min_nodes_for_reliable else 'low'

    # 1. Spacing uniformity (coefficient of variation)
    if edges:
        spacings = [e.edge_distance_um for e in edges if e.edge_distance_um > 0]
        if spacings:
            mean_spacing = np.mean(spacings)
            std_spacing = np.std(spacings)
            cv = std_spacing / mean_spacing if mean_spacing > 0 else 1.0
            result['spacing_cv'] = float(cv)
            # Score: CV of 0 = perfect (1.0), CV of 0.5+ = poor (0.0)
            result['spacing_uniformity'] = float(max(0, 1 - 2 * cv))

    # 2. Degree distribution (neighbors per node)
    degree = defaultdict(int)
    tubercle_ids = {t.id for t in tubercles}

    for e in edges:
        if e.tubercle_a_id in tubercle_ids:
            degree[e.tubercle_a_id] += 1
        if e.tubercle_b_id in tubercle_ids:
            degree[e.tubercle_b_id] += 1

    # Include nodes with 0 connections
    for t in tubercles:
        if t.id not in degree:
            degree[t.id] = 0

    degrees = list(degree.values())
    if degrees:
        result['mean_degree'] = float(np.mean(degrees))

        # Build histogram
        histogram = defaultdict(int)
        for d in degrees:
            histogram[d] += 1
        result['degree_histogram'] = dict(histogram)

        # Score: fraction of nodes with 4-8 neighbors (allowing for edge effects)
        # Interior hex nodes have 6, edge nodes have 3-5
        good_count = sum(1 for d in degrees if 4 <= d <= 8)
        acceptable_count = sum(1 for d in degrees if 3 <= d <= 9)

        # Use a weighted score: full credit for 5-7, partial for 3-4 and 8-9
        weighted_score = 0
        for d in degrees:
            if 5 <= d <= 7:
                weighted_score += 1.0
            elif d == 4 or d == 8:
                weighted_score += 0.7
            elif d == 3 or d == 9:
                weighted_score += 0.3
            # 0-2 or 10+ get 0

        result['degree_score'] = float(weighted_score / len(degrees))

    # 3. Edge/node ratio (ideal is ~3 for hex lattice)
    # For a planar graph: E ≤ 3V - 6 (equality for triangulation)
    # Hex lattice interior: each node has 6 edges, each edge shared by 2 nodes = 3 edges/node
    n_nodes = len(tubercles)
    n_edges = len(edges)
    if n_nodes > 0:
        ratio = n_edges / n_nodes
        # Ideal is ~3, but with edge effects it's often 2-2.5
        # Score: ratio of 2.5-3.5 is good, outside that degrades
        ideal_ratio = 2.5  # Account for edge effects
        deviation = abs(ratio - ideal_ratio)
        result['edge_ratio_score'] = float(max(0, 1 - deviation / 2))

    # 4. Composite hexagonalness score
    # Weight: spacing uniformity and degree are most important
    score = (
        0.40 * result['spacing_uniformity'] +
        0.45 * result['degree_score'] +
        0.15 * result['edge_ratio_score']
    )
    result['hexagonalness_score'] = float(score)

    return result


def classify_genus(
    mean_diameter: float,
    mean_space: float,
) -> Tuple[str, str]:
    """
    Classify genus based on tubercle metrics.

    Uses reference ranges from Gayet & Meunier papers.

    Args:
        mean_diameter: Mean tubercle diameter in µm
        mean_space: Mean intertubercular space in µm

    Returns:
        Tuple of (genus name, confidence level)
    """
    best_match = None
    best_score = float("inf")

    for genus, ranges in GENUS_REFERENCE_RANGES.items():
        # Check if values fall within range
        diam_in_range = ranges["diameter_min"] <= mean_diameter <= ranges["diameter_max"]
        space_in_range = ranges["space_min"] <= mean_space <= ranges["space_max"]

        if diam_in_range and space_in_range:
            # Perfect match
            return genus, "high"

        # Calculate distance from range center for partial matches
        diam_center = (ranges["diameter_min"] + ranges["diameter_max"]) / 2
        space_center = (ranges["space_min"] + ranges["space_max"]) / 2

        # Normalize distances by range size
        diam_range = ranges["diameter_max"] - ranges["diameter_min"]
        space_range = ranges["space_max"] - ranges["space_min"]

        if diam_range > 0 and space_range > 0:
            diam_dist = abs(mean_diameter - diam_center) / diam_range
            space_dist = abs(mean_space - space_center) / space_range
            score = diam_dist + space_dist

            if score < best_score:
                best_score = score
                best_match = genus

    if best_match and best_score < 1.5:
        return best_match, "medium"
    elif best_match and best_score < 3.0:
        return best_match, "low"
    else:
        return "Unknown", "none"


def measure_metrics(
    tubercles: List[Tubercle],
    calibration: CalibrationData,
    image_path: str = "",
    graph_type: str = "delaunay",
    max_distance_factor: Optional[float] = None,
    spacing_method: str = "nearest",
) -> MeasurementResult:
    """
    Calculate all metrics for detected tubercles.

    Args:
        tubercles: List of detected tubercles
        calibration: Calibration data
        image_path: Path to source image (for record keeping)
        graph_type: Type of neighbor graph for spacing calculation:
            - "delaunay": Full Delaunay triangulation (default)
            - "gabriel": Gabriel graph (fewer long edges)
            - "rng": Relative Neighborhood Graph (most conservative)
        max_distance_factor: If set, filter out edges longer than this factor
            times the median edge length. E.g., 1.5 removes outliers > 1.5× median.
        spacing_method: Method for calculating intertubercular spacing:
            - "nearest": Use nearest-neighbor distances only (matches Gayet & Meunier
              methodology - recommended for comparison with published values)
            - "graph": Use all edges from the neighbor graph

    Returns:
        MeasurementResult with all metrics
    """
    # Build neighbor graph
    triangulation = build_neighbor_graph(tubercles)

    # Get neighbor edges
    if triangulation is not None:
        edges = get_neighbor_edges(
            tubercles, triangulation, calibration, graph_type, max_distance_factor
        )
    else:
        edges = []

    # Measure diameters
    diameters, mean_diam, std_diam = measure_diameters(tubercles)

    # Measure intertubercular spaces
    if spacing_method == "nearest":
        # Use nearest-neighbor method (matches paper methodology)
        spaces, mean_space, std_space = measure_nearest_neighbor_spacing(
            tubercles, calibration
        )
    else:
        # Use graph-based method (all edges from triangulation)
        spaces, mean_space, std_space = measure_intertubercular_spaces(edges)

    # Classify genus
    if tubercles:
        genus, confidence = classify_genus(mean_diam, mean_space)
    else:
        genus, confidence = "Unknown", "none"

    return MeasurementResult(
        image_path=image_path,
        calibration=calibration,
        n_tubercles=len(tubercles),
        tubercles=tubercles,
        neighbor_edges=edges,
        tubercle_diameters_um=diameters,
        mean_diameter_um=mean_diam,
        std_diameter_um=std_diam,
        intertubercular_spaces_um=spaces,
        mean_space_um=mean_space,
        std_space_um=std_space,
        suggested_genus=genus,
        classification_confidence=confidence,
    )


def process_image(
    image_path: Path,
    scale_bar_um: Optional[float] = None,
    scale_bar_px: Optional[float] = None,
    min_diameter_um: float = 2.0,
    max_diameter_um: float = 10.0,
    detection_threshold: float = 0.05,
    min_circularity: float = 0.5,
) -> Tuple[MeasurementResult, np.ndarray, dict]:
    """
    Process a single image end-to-end.

    Main entry point for image processing.

    Args:
        image_path: Path to image file
        scale_bar_um: Scale bar length in µm (None for auto-estimate)
        scale_bar_px: Scale bar length in pixels (required if scale_bar_um provided)
        min_diameter_um: Minimum expected tubercle diameter
        max_diameter_um: Maximum expected tubercle diameter
        detection_threshold: Blob detection threshold
        min_circularity: Minimum circularity filter

    Returns:
        Tuple of (MeasurementResult, preprocessed_image, processing_info)
    """
    info = {"image_path": str(image_path)}

    # Load image
    image = load_image(image_path)
    info["image_shape"] = image.shape

    # Calibration
    if scale_bar_um is not None and scale_bar_px is not None:
        calibration = calibrate_manual(scale_bar_um, scale_bar_px)
    else:
        calibration = estimate_calibration_700x(image.shape[1])
        info["calibration_warning"] = "Using estimated calibration for 700x magnification"

    info["calibration"] = {
        "um_per_pixel": calibration.um_per_pixel,
        "method": calibration.method,
    }

    # Preprocess
    preprocessed, intermediates = preprocess_pipeline(image)
    info["preprocessing"] = "CLAHE + Gaussian blur"

    # Detect tubercles
    tubercles = detect_tubercles(
        preprocessed,
        calibration,
        min_diameter_um=min_diameter_um,
        max_diameter_um=max_diameter_um,
        threshold=detection_threshold,
        min_circularity=min_circularity,
    )
    info["n_tubercles_detected"] = len(tubercles)

    # Measure metrics
    result = measure_metrics(
        tubercles,
        calibration,
        image_path=str(image_path),
    )

    info["mean_diameter_um"] = result.mean_diameter_um
    info["mean_space_um"] = result.mean_space_um
    info["suggested_genus"] = result.suggested_genus

    return result, preprocessed, info
