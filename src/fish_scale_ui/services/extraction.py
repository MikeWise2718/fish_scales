"""Extraction service - wrapper around CLI core modules."""

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from fish_scale_analysis.models import CalibrationData, Tubercle, NeighborEdge
from fish_scale_analysis.core.preprocessing import load_image, preprocess_pipeline
from fish_scale_analysis.core.detection import detect_tubercles
from fish_scale_analysis.core.measurement import (
    build_neighbor_graph,
    find_boundary_nodes,
    get_neighbor_edges,
    measure_diameters,
    measure_nearest_neighbor_spacing,
    measure_intertubercular_spaces,
    classify_genus,
    calculate_hexagonalness,
)
from fish_scale_analysis.profiles import PROFILES, get_profile


def run_extraction(
    image_path: str,
    um_per_px: float,
    method: str = "log",
    threshold: float = 0.05,
    min_diameter_um: float = 2.0,
    max_diameter_um: float = 10.0,
    min_circularity: float = 0.5,
    clahe_clip: float = 0.03,
    clahe_kernel: int = 8,
    blur_sigma: float = 1.0,
    neighbor_graph: str = "delaunay",
    edge_margin_px: int = 10,
    refine_ellipse: bool = True,
    cull_long_edges: bool = True,
    cull_factor: float = 1.8,
) -> dict:
    """
    Run tubercle extraction on an image.

    Args:
        image_path: Path to the image file
        um_per_px: Calibration in micrometers per pixel
        method: Detection method (log, dog, ellipse, lattice)
        threshold: Detection threshold
        min_diameter_um: Minimum tubercle diameter
        max_diameter_um: Maximum tubercle diameter
        min_circularity: Minimum circularity filter
        clahe_clip: CLAHE clip limit
        clahe_kernel: CLAHE kernel size
        blur_sigma: Gaussian blur sigma
        neighbor_graph: Graph type (delaunay, gabriel, rng)
        edge_margin_px: Edge margin in pixels
        refine_ellipse: Whether to fit ellipses for more accurate measurements
        cull_long_edges: Whether to remove edges longer than cull_factor * average
        cull_factor: Factor for edge length culling (e.g., 1.8 = remove edges > 1.8x average)

    Returns:
        Dictionary with extraction results
    """
    # Create calibration data
    calibration = CalibrationData(
        um_per_pixel=um_per_px,
        scale_bar_length_um=0,
        scale_bar_length_px=0,
        method="manual"
    )

    # Load and preprocess image
    image = load_image(Path(image_path))
    preprocessed, _ = preprocess_pipeline(
        image,
        clahe_clip=clahe_clip,
        clahe_kernel=clahe_kernel,
        blur_sigma=blur_sigma,
    )

    # Detect tubercles
    tubercles = detect_tubercles(
        preprocessed,
        calibration,
        min_diameter_um=min_diameter_um,
        max_diameter_um=max_diameter_um,
        threshold=threshold,
        min_circularity=min_circularity,
        edge_margin_px=edge_margin_px,
        method=method,
        refine_ellipse=refine_ellipse,
    )

    # Build neighbor graph and get edges
    triangulation = build_neighbor_graph(tubercles)
    edges = []
    boundary_indices = set()
    if triangulation is not None:
        edges = get_neighbor_edges(
            tubercles,
            triangulation,
            calibration,
            graph_type=neighbor_graph,
        )
        # Find boundary nodes using Delaunay triangulation
        boundary_indices = find_boundary_nodes(triangulation)

    # Measure statistics
    diameters, mean_diam, std_diam = measure_diameters(tubercles)

    # Cull long edges if enabled (do this BEFORE statistics calculation)
    if cull_long_edges and edges:
        center_distances = [e.center_distance_um for e in edges]
        avg_center_distance = np.mean(center_distances)
        max_allowed = avg_center_distance * cull_factor
        edges = [e for e in edges if e.center_distance_um <= max_allowed]

    # Calculate edge statistics (using potentially culled edges)
    if edges:
        edge_distances = [e.edge_distance_um for e in edges]
        mean_space = np.mean(edge_distances)
        std_space = np.std(edge_distances)
    else:
        spaces, mean_space, std_space = measure_nearest_neighbor_spacing(
            tubercles, calibration
        )

    # Classify genus
    genus = "Unknown"
    confidence = "none"
    if tubercles:
        genus, confidence = classify_genus(mean_diam, mean_space)

    # Calculate hexagonalness metrics (using culled edges for consistency with JS)
    hex_metrics = calculate_hexagonalness(tubercles, edges)

    # Convert to serializable format
    # Build a mapping from tubercle ID to index for boundary lookup
    id_to_index = {t.id: idx for idx, t in enumerate(tubercles)}

    tubercles_data = []
    for t in tubercles:
        idx = id_to_index.get(t.id, -1)
        tub_data = {
            'id': t.id,
            'centroid_x': t.centroid[0],
            'centroid_y': t.centroid[1],
            'diameter_px': t.diameter_px,
            'diameter_um': t.diameter_um,
            'radius_px': t.radius_px,
            'circularity': t.circularity,
            'source': 'extracted',  # Track origin for coloring
            'is_boundary': idx in boundary_indices,
        }
        # Include ellipse parameters if available
        if t.major_axis_px is not None:
            tub_data['major_axis_px'] = t.major_axis_px
            tub_data['minor_axis_px'] = t.minor_axis_px
            tub_data['major_axis_um'] = t.major_axis_um
            tub_data['minor_axis_um'] = t.minor_axis_um
            tub_data['orientation'] = t.orientation  # radians
            tub_data['eccentricity'] = t.eccentricity
        tubercles_data.append(tub_data)

    edges_data = []
    for e in edges:
        # Get centroid coordinates for the edge endpoints
        tub_a = next((t for t in tubercles if t.id == e.tubercle_a_id), None)
        tub_b = next((t for t in tubercles if t.id == e.tubercle_b_id), None)
        if tub_a and tub_b:
            edges_data.append({
                'id1': e.tubercle_a_id,
                'id2': e.tubercle_b_id,
                'x1': tub_a.centroid[0],
                'y1': tub_a.centroid[1],
                'x2': tub_b.centroid[0],
                'y2': tub_b.centroid[1],
                'center_distance_um': e.center_distance_um,
                'edge_distance_um': e.edge_distance_um,
            })

    return {
        'success': True,
        'tubercles': tubercles_data,
        'edges': edges_data,
        'statistics': {
            'n_tubercles': len(tubercles),
            'n_edges': len(edges_data),  # Use culled count
            'n_boundary': len(boundary_indices),
            'n_interior': len(tubercles) - len(boundary_indices),
            'mean_diameter_um': round(mean_diam, 2),
            'std_diameter_um': round(std_diam, 2),
            'mean_space_um': round(mean_space, 2),
            'std_space_um': round(std_space, 2),
            'suggested_genus': genus,
            'classification_confidence': confidence,
            # Hexagonalness metrics
            'hexagonalness_score': round(hex_metrics['hexagonalness_score'], 3),
            'spacing_uniformity': round(hex_metrics['spacing_uniformity'], 3),
            'degree_score': round(hex_metrics['degree_score'], 3),
            'mean_degree': round(hex_metrics['mean_degree'], 2),
            'spacing_cv': round(hex_metrics['spacing_cv'], 3),
            'reliability': hex_metrics['reliability'],
            'n_nodes': hex_metrics['n_nodes'],
        },
        'parameters': {
            'method': method,
            'threshold': threshold,
            'min_diameter_um': min_diameter_um,
            'max_diameter_um': max_diameter_um,
            'min_circularity': min_circularity,
            'clahe_clip': clahe_clip,
            'clahe_kernel': clahe_kernel,
            'blur_sigma': blur_sigma,
            'neighbor_graph': neighbor_graph,
        }
    }


def get_profiles_list() -> list:
    """Get list of available profiles with their parameters."""
    profiles = []
    for name, profile in PROFILES.items():
        profiles.append({
            'name': name,
            'description': profile.description,
            'calibration_um_per_px': profile.calibration_um_per_px,
            'clahe_clip': profile.clahe_clip,
            'clahe_kernel': profile.clahe_kernel,
            'blur_sigma': profile.blur_sigma,
            'threshold': profile.threshold,
            'min_circularity': profile.min_circularity,
            'min_diameter_um': profile.min_diameter_um,
            'max_diameter_um': profile.max_diameter_um,
        })
    return profiles


def analyze_point_for_tubercle(
    image_path: str,
    x: float,
    y: float,
    um_per_px: float,
    method: str = "log",
    threshold: float = 0.05,
    min_diameter_um: float = 2.0,
    max_diameter_um: float = 10.0,
    min_circularity: float = 0.5,
    clahe_clip: float = 0.03,
    clahe_kernel: int = 8,
    blur_sigma: float = 1.0,
    region_factor: float = 6.0,
) -> dict:
    """
    Analyze a point in the image to detect if there's a tubercle there.

    Extracts a region around (x, y), runs blob detection, and returns
    the closest blob to the click point.

    Args:
        image_path: Path to the image file
        x: X coordinate of the click point (in pixels)
        y: Y coordinate of the click point (in pixels)
        um_per_px: Calibration in micrometers per pixel
        method: Detection method (log, dog, ellipse, lattice)
        threshold: Detection threshold
        min_diameter_um: Minimum tubercle diameter in micrometers
        max_diameter_um: Maximum tubercle diameter in micrometers
        min_circularity: Minimum circularity filter
        clahe_clip: CLAHE clip limit
        clahe_kernel: CLAHE kernel size
        blur_sigma: Gaussian blur sigma

    Returns:
        Dictionary with detection results:
        - success: True
        - detected: True/False
        - If detected: diameter_px, diameter_um, radius_px, center_x, center_y, circularity
        - If not detected: reason (no_blob_found or click_not_on_blob)
    """
    # Calculate region size based on max_diameter and region_factor
    # Larger factor = more stable detection with sufficient context for CLAHE
    max_diameter_px = max_diameter_um / um_per_px
    region_size = int(max_diameter_px * region_factor)
    # Minimum region must fit the max blob; maximum prevents slowdown
    min_size = max(30, int(max_diameter_px * 1.5))  # At least 1.5x the max blob size
    max_size = 600
    region_size = max(min_size, min(max_size, region_size))

    # Load image
    image = load_image(Path(image_path))
    h, w = image.shape[:2]

    # Calculate region bounds (centered on click point)
    half = region_size // 2
    x_min = max(0, int(x - half))
    x_max = min(w, int(x + half))
    y_min = max(0, int(y - half))
    y_max = min(h, int(y + half))

    # Extract and preprocess region
    region = image[y_min:y_max, x_min:x_max]
    preprocessed, _ = preprocess_pipeline(
        region,
        clahe_clip=clahe_clip,
        clahe_kernel=clahe_kernel,
        blur_sigma=blur_sigma,
    )

    # Create local calibration for the region
    calibration = CalibrationData(
        um_per_pixel=um_per_px,
        scale_bar_length_um=0,
        scale_bar_length_px=0,
        method="manual"
    )

    # Detect tubercles in the region
    tubercles = detect_tubercles(
        preprocessed,
        calibration,
        min_diameter_um=min_diameter_um,
        max_diameter_um=max_diameter_um,
        threshold=threshold,
        min_circularity=min_circularity,
        edge_margin_px=0,  # Don't exclude edges in small region
        method=method,
        refine_ellipse=True,
    )

    # Region bounds for visual feedback
    region_bounds = {
        "x_min": x_min,
        "y_min": y_min,
        "x_max": x_max,
        "y_max": y_max,
    }

    # Convert all detected blobs to global coordinates for visualization
    all_blobs = []
    for tub in tubercles:
        all_blobs.append({
            "center_x": float(tub.centroid[0] + x_min),
            "center_y": float(tub.centroid[1] + y_min),
            "radius_px": float(tub.radius_px),
        })

    if not tubercles:
        return {"success": True, "detected": False, "reason": "no_blob_found", "region": region_bounds, "all_blobs": []}

    # Find the blob closest to the click point (in local coordinates)
    click_local_x = x - x_min
    click_local_y = y - y_min

    closest = None
    closest_dist = float('inf')

    for tub in tubercles:
        dx = tub.centroid[0] - click_local_x
        dy = tub.centroid[1] - click_local_y
        dist = (dx**2 + dy**2) ** 0.5
        if dist < closest_dist:
            closest_dist = dist
            closest = tub

    # Check if closest blob is within reasonable distance
    # (should be within the detected radius)
    if closest_dist > closest.radius_px * 1.5:
        return {"success": True, "detected": False, "reason": "click_not_on_blob", "region": region_bounds, "all_blobs": all_blobs}

    # Convert center back to global coordinates
    global_x = closest.centroid[0] + x_min
    global_y = closest.centroid[1] + y_min

    result = {
        "success": True,
        "detected": True,
        "diameter_px": closest.diameter_px,
        "diameter_um": closest.diameter_um,
        "radius_px": closest.radius_px,
        "center_x": global_x,
        "center_y": global_y,
        "circularity": closest.circularity,
        "region": region_bounds,
        "all_blobs": all_blobs,
    }

    # Include ellipse parameters if available
    if closest.major_axis_px is not None:
        result["major_axis_px"] = closest.major_axis_px
        result["minor_axis_px"] = closest.minor_axis_px
        result["major_axis_um"] = closest.major_axis_um
        result["minor_axis_um"] = closest.minor_axis_um
        result["orientation"] = closest.orientation
        result["eccentricity"] = closest.eccentricity

    return result
