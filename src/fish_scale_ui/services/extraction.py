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
    get_neighbor_edges,
    measure_diameters,
    measure_nearest_neighbor_spacing,
    measure_intertubercular_spaces,
    classify_genus,
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
    )

    # Build neighbor graph and get edges
    triangulation = build_neighbor_graph(tubercles)
    edges = []
    if triangulation is not None:
        edges = get_neighbor_edges(
            tubercles,
            triangulation,
            calibration,
            graph_type=neighbor_graph,
        )

    # Measure statistics
    diameters, mean_diam, std_diam = measure_diameters(tubercles)
    spaces, mean_space, std_space = measure_nearest_neighbor_spacing(
        tubercles, calibration
    )

    # Classify genus
    genus = "Unknown"
    confidence = "none"
    if tubercles:
        genus, confidence = classify_genus(mean_diam, mean_space)

    # Convert to serializable format
    tubercles_data = []
    for t in tubercles:
        tubercles_data.append({
            'id': t.id,
            'centroid_x': t.centroid[0],
            'centroid_y': t.centroid[1],
            'diameter_px': t.diameter_px,
            'diameter_um': t.diameter_um,
            'radius_px': t.radius_px,
            'circularity': t.circularity,
        })

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
            'n_edges': len(edges),
            'mean_diameter_um': round(mean_diam, 2),
            'std_diameter_um': round(std_diam, 2),
            'mean_space_um': round(mean_space, 2),
            'std_space_um': round(std_space, 2),
            'suggested_genus': genus,
            'classification_confidence': confidence,
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
