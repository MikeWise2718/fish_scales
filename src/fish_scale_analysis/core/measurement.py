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
