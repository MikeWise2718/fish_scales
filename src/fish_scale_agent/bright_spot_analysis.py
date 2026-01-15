"""Bright spot detection analysis and evaluation.

This module provides functions to evaluate how accurately the VLM placed
tubercle markers at actual bright spots in the image.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class BrightSpotAnalysis:
    """Results of bright spot detection analysis."""

    spots_placed: int
    spots_expected: int
    separation_violations: int
    mean_intensity: float
    intensity_std: float
    intensity_ranking_score: float
    min_separation_requested: int
    violations_detail: list[dict]  # List of violation pairs


def evaluate_bright_spot_detection(
    placed_spots: list[dict],
    image_path: str | Path,
    expected_count: int,
    min_separation: int,
) -> dict:
    """Evaluate bright spot detection accuracy.

    Args:
        placed_spots: List of placed tubercles with 'centroid_x' and 'centroid_y' keys
        image_path: Path to the image file
        expected_count: Target number of spots (N)
        min_separation: Minimum pixel separation requested

    Returns:
        Analysis results dictionary with:
        - spots_placed: Number of spots placed
        - spots_expected: Target count
        - separation_violations: Number of spot pairs < min_separation apart
        - mean_intensity: Average pixel intensity at spot centers
        - intensity_std: Standard deviation of intensities
        - intensity_ranking_score: 0-1, how well we found the truly brightest spots
        - violations_detail: List of violation pairs with distances
    """
    try:
        from PIL import Image
    except ImportError:
        return {
            "error": "PIL not available for image analysis",
            "spots_placed": len(placed_spots),
            "spots_expected": expected_count,
        }

    # Load image and convert to grayscale
    try:
        img = Image.open(image_path).convert('L')
        img_array = np.array(img)
    except Exception as e:
        return {
            "error": f"Failed to load image: {e}",
            "spots_placed": len(placed_spots),
            "spots_expected": expected_count,
        }

    results = {
        "spots_placed": len(placed_spots),
        "spots_expected": expected_count,
        "min_separation_requested": min_separation,
    }

    if len(placed_spots) == 0:
        results.update({
            "separation_violations": 0,
            "mean_intensity": 0,
            "intensity_std": 0,
            "intensity_ranking_score": 0,
            "violations_detail": [],
            "diagnosis": "No spots placed",
        })
        return results

    # Extract coordinates
    spots = []
    for spot in placed_spots:
        x = spot.get('centroid_x', spot.get('x', 0))
        y = spot.get('centroid_y', spot.get('y', 0))
        spots.append((x, y))

    # Check separations
    violations = 0
    violations_detail = []
    for i, s1 in enumerate(spots):
        for j, s2 in enumerate(spots[i+1:], i+1):
            dist = np.sqrt((s1[0] - s2[0])**2 + (s1[1] - s2[1])**2)
            if dist < min_separation:
                violations += 1
                violations_detail.append({
                    "spot1_idx": i,
                    "spot2_idx": j,
                    "distance": round(dist, 1),
                    "required": min_separation,
                })
    results["separation_violations"] = violations
    results["violations_detail"] = violations_detail

    # Sample intensity at placed spots
    intensities = []
    for x, y in spots:
        xi, yi = int(x), int(y)
        if 0 <= xi < img_array.shape[1] and 0 <= yi < img_array.shape[0]:
            # Average intensity in 5x5 region around center
            y_start = max(0, yi - 2)
            y_end = min(img_array.shape[0], yi + 3)
            x_start = max(0, xi - 2)
            x_end = min(img_array.shape[1], xi + 3)
            region = img_array[y_start:y_end, x_start:x_end]
            if region.size > 0:
                intensities.append(np.mean(region))

    if intensities:
        results["mean_intensity"] = round(float(np.mean(intensities)), 1)
        results["intensity_std"] = round(float(np.std(intensities)), 1)
    else:
        results["mean_intensity"] = 0
        results["intensity_std"] = 0

    # Calculate intensity ranking score
    # This measures how well the placed spots correspond to truly bright regions
    if intensities and len(intensities) > 0:
        # Find what percentile of brightness our spots fall into
        flat = img_array.flatten()
        percentiles = []
        for intensity in intensities:
            # What percentage of pixels are dimmer than this spot?
            pct = np.sum(flat < intensity) / len(flat) * 100
            percentiles.append(pct)

        # Score is average percentile (higher = we found brighter spots)
        # Normalize to 0-1 range where 1.0 means all spots were in top percentiles
        avg_percentile = np.mean(percentiles)
        # Convert to score: 95th percentile = 0.9 score, 50th = 0.0, etc.
        ranking_score = max(0, (avg_percentile - 50) / 50)
        results["intensity_ranking_score"] = round(ranking_score, 3)
        results["avg_brightness_percentile"] = round(avg_percentile, 1)
    else:
        results["intensity_ranking_score"] = 0
        results["avg_brightness_percentile"] = 0

    # Generate diagnosis
    diagnosis_parts = []

    # Count accuracy
    if results["spots_placed"] == expected_count:
        diagnosis_parts.append(f"Found exactly {expected_count} spots")
    elif results["spots_placed"] < expected_count:
        diagnosis_parts.append(f"Found only {results['spots_placed']}/{expected_count} spots")
    else:
        diagnosis_parts.append(f"Found {results['spots_placed']} spots (requested {expected_count})")

    # Separation compliance
    if violations == 0:
        diagnosis_parts.append("All spots meet minimum separation")
    else:
        diagnosis_parts.append(f"{violations} pairs violate {min_separation}px separation")

    # Brightness quality
    score = results["intensity_ranking_score"]
    if score >= 0.8:
        diagnosis_parts.append("Excellent brightness targeting")
    elif score >= 0.6:
        diagnosis_parts.append("Good brightness targeting")
    elif score >= 0.4:
        diagnosis_parts.append("Moderate brightness targeting")
    else:
        diagnosis_parts.append("Poor brightness targeting - spots may not be at bright regions")

    results["diagnosis"] = "; ".join(diagnosis_parts)

    return results


def format_bright_spot_report(analysis: dict) -> str:
    """Format bright spot analysis as a human-readable report.

    Args:
        analysis: Analysis dict from evaluate_bright_spot_detection

    Returns:
        Formatted report string
    """
    lines = [
        "=" * 50,
        "BRIGHT SPOT DETECTION ANALYSIS",
        "=" * 50,
        "",
    ]

    # Basic counts
    lines.append(f"Spots placed: {analysis.get('spots_placed', 0)}")
    lines.append(f"Spots expected: {analysis.get('spots_expected', 0)}")
    lines.append("")

    # Separation analysis
    violations = analysis.get('separation_violations', 0)
    min_sep = analysis.get('min_separation_requested', 30)
    lines.append(f"Minimum separation requested: {min_sep}px")
    if violations == 0:
        lines.append("Separation compliance: PASS (all spots meet minimum)")
    else:
        lines.append(f"Separation compliance: FAIL ({violations} violations)")
        for v in analysis.get('violations_detail', [])[:5]:  # Show first 5
            lines.append(f"  - Spots {v['spot1_idx']} and {v['spot2_idx']}: {v['distance']:.1f}px apart")
    lines.append("")

    # Intensity analysis
    lines.append(f"Mean intensity at spots: {analysis.get('mean_intensity', 0):.1f} (0-255)")
    lines.append(f"Intensity std dev: {analysis.get('intensity_std', 0):.1f}")
    lines.append(f"Brightness percentile: {analysis.get('avg_brightness_percentile', 0):.1f}%")
    lines.append(f"Brightness ranking score: {analysis.get('intensity_ranking_score', 0):.3f}")
    lines.append("")

    # Diagnosis
    lines.append("DIAGNOSIS:")
    lines.append(analysis.get('diagnosis', 'No diagnosis available'))
    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)
