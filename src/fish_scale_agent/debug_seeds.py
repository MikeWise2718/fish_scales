"""Debug seed tubercles for coordinate system verification.

This module provides functionality for placing debug seed tubercles at known
positions before running the AgenticEditing agent. These seeds help diagnose
whether the VLM correctly understands and uses the image coordinate system.

See specs/debug-seeds.md for full specification.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SeedPosition:
    """A single seed position with metadata."""

    x: float
    y: float
    label: str
    index: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "expected": [self.x, self.y],
            "label": self.label,
            "index": self.index,
        }


@dataclass
class ImageIdentity:
    """Identity fingerprint for an image file."""

    path: str
    dimensions: tuple[int, int]
    hash_sha256: str
    file_size_bytes: int
    file_mtime: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "dimensions": list(self.dimensions),
            "hash_sha256": self.hash_sha256,
            "file_size_bytes": self.file_size_bytes,
            "file_mtime": self.file_mtime,
        }

    def matches(self, other: "ImageIdentity") -> bool:
        """Check if this identity matches another."""
        return self.hash_sha256 == other.hash_sha256


@dataclass
class DebugSeedConfig:
    """Configuration for debug seeds."""

    pattern: str  # "corners", "grid3x3", "cross", or custom coords
    radius: float = 15.0  # Seed radius in pixels
    positions: list[SeedPosition] = field(default_factory=list)
    image_identity: ImageIdentity | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "enabled": True,
            "seed_pattern": self.pattern,
            "seed_radius": self.radius,
            "image_identity": self.image_identity.to_dict() if self.image_identity else None,
            "seeds_placed": [p.to_dict() for p in self.positions],
        }


def compute_image_identity(image_path: str | Path) -> ImageIdentity:
    """Compute identity fingerprint for an image file.

    Args:
        image_path: Path to the image file

    Returns:
        ImageIdentity with hash, dimensions, and file metadata
    """
    from PIL import Image

    path = Path(image_path)

    # Read image and compute hash of pixel data
    with Image.open(path) as img:
        # Convert to RGB to ensure consistent hashing regardless of mode
        if img.mode != "RGB":
            img_rgb = img.convert("RGB")
        else:
            img_rgb = img
        img_bytes = img_rgb.tobytes()
        hash_sha256 = hashlib.sha256(img_bytes).hexdigest()
        dimensions = (img.width, img.height)

    # File metadata
    stat = path.stat()

    return ImageIdentity(
        path=str(path.resolve()),
        dimensions=dimensions,
        hash_sha256=hash_sha256,
        file_size_bytes=stat.st_size,
        file_mtime=datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z",
    )


def get_seed_positions(
    pattern: str,
    width: int,
    height: int,
    margin_percent: float = 15.0,
) -> list[SeedPosition]:
    """Calculate seed positions for a given pattern and image dimensions.

    Args:
        pattern: Pattern name ("corners", "grid3x3", "cross") or custom coords
                 Custom format: "x1,y1;x2,y2;x3,y3" (semicolon-separated pairs)
        width: Image width in pixels
        height: Image height in pixels
        margin_percent: Margin from edges as percentage (default 15%)

    Returns:
        List of SeedPosition objects
    """
    # Calculate margins
    margin_x = width * margin_percent / 100
    margin_y = height * margin_percent / 100

    # Interior bounds
    left = margin_x
    right = width - margin_x
    top = margin_y
    bottom = height - margin_y
    center_x = width / 2
    center_y = height / 2

    positions: list[SeedPosition] = []

    if pattern == "corners":
        # 4 corners + center (5 points)
        positions = [
            SeedPosition(x=left, y=top, label="top-left", index=0),
            SeedPosition(x=right, y=top, label="top-right", index=1),
            SeedPosition(x=left, y=bottom, label="bottom-left", index=2),
            SeedPosition(x=right, y=bottom, label="bottom-right", index=3),
            SeedPosition(x=center_x, y=center_y, label="center", index=4),
        ]

    elif pattern == "grid3x3":
        # 3x3 grid (9 points) at 20%, 50%, 80%
        x_positions = [width * 0.2, width * 0.5, width * 0.8]
        y_positions = [height * 0.2, height * 0.5, height * 0.8]
        labels = [
            ["top-left", "top-center", "top-right"],
            ["middle-left", "center", "middle-right"],
            ["bottom-left", "bottom-center", "bottom-right"],
        ]
        index = 0
        for yi, y in enumerate(y_positions):
            for xi, x in enumerate(x_positions):
                positions.append(
                    SeedPosition(x=x, y=y, label=labels[yi][xi], index=index)
                )
                index += 1

    elif pattern == "cross":
        # Center + 4 cardinal points (5 points)
        positions = [
            SeedPosition(x=center_x, y=center_y, label="center", index=0),
            SeedPosition(x=center_x, y=top, label="north", index=1),
            SeedPosition(x=right, y=center_y, label="east", index=2),
            SeedPosition(x=center_x, y=bottom, label="south", index=3),
            SeedPosition(x=left, y=center_y, label="west", index=4),
        ]

    else:
        # Try to parse as custom coordinates: "x1,y1;x2,y2;..."
        positions = parse_custom_positions(pattern)

    return positions


def parse_custom_positions(coords_str: str) -> list[SeedPosition]:
    """Parse custom coordinate string into seed positions.

    Args:
        coords_str: Format "x1,y1;x2,y2;x3,y3" (semicolon-separated x,y pairs)

    Returns:
        List of SeedPosition objects

    Raises:
        ValueError: If the format is invalid
    """
    positions = []
    pairs = coords_str.strip().split(";")

    for i, pair in enumerate(pairs):
        pair = pair.strip()
        if not pair:
            continue

        parts = pair.split(",")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid coordinate pair '{pair}'. Expected 'x,y' format."
            )

        try:
            x = float(parts[0].strip())
            y = float(parts[1].strip())
        except ValueError as e:
            raise ValueError(
                f"Invalid coordinate values in '{pair}': {e}"
            )

        positions.append(
            SeedPosition(x=x, y=y, label=f"custom-{i}", index=i)
        )

    if not positions:
        raise ValueError("No valid coordinates found in pattern string")

    return positions


def create_seed_tubercle(
    position: SeedPosition,
    tubercle_id: int,
    radius_px: float,
    calibration_um_per_px: float,
    pattern: str,
) -> dict:
    """Create a tubercle dict for a seed position.

    Args:
        position: The seed position
        tubercle_id: ID to assign to this tubercle
        radius_px: Radius in pixels
        calibration_um_per_px: Calibration for um conversion
        pattern: Pattern name for metadata

    Returns:
        Tubercle dict compatible with the annotation format
    """
    diameter_px = radius_px * 2
    diameter_um = diameter_px * calibration_um_per_px

    return {
        "id": tubercle_id,
        "centroid_x": position.x,
        "centroid_y": position.y,
        "radius_px": radius_px,
        "diameter_px": diameter_px,
        "diameter_um": diameter_um,
        "circularity": 1.0,
        "source": "debug_seed",
        "_debug": {
            "seed_index": position.index,
            "pattern": pattern,
            "expected_x": position.x,
            "expected_y": position.y,
            "description": position.label,
        },
    }


def format_seed_list_for_prompt(positions: list[SeedPosition]) -> str:
    """Format seed positions for inclusion in the system prompt.

    Args:
        positions: List of seed positions

    Returns:
        Formatted string listing all seed positions
    """
    lines = []
    for pos in positions:
        lines.append(f"- Seed {pos.index} ({pos.label}): ({pos.x:.0f}, {pos.y:.0f})")
    return "\n".join(lines)


def validate_pattern(pattern: str) -> bool:
    """Check if a pattern string is valid.

    Args:
        pattern: Pattern name or custom coordinates

    Returns:
        True if valid, False otherwise
    """
    if pattern in ("corners", "grid3x3", "cross"):
        return True

    # Try parsing as custom coordinates
    try:
        positions = parse_custom_positions(pattern)
        return len(positions) > 0
    except ValueError:
        return False


# ============================================================================
# Phase 3: Analysis Functions
# ============================================================================

import re
import math
from dataclasses import dataclass as analysis_dataclass


@analysis_dataclass
class AnalysisResult:
    """Complete analysis result for debug seed session."""

    seeds_placed: int
    vlm_tubercles_added: int
    image_identity: dict
    vlm_reported_seeds: bool
    vlm_seed_positions_reported: list[dict]
    vlm_image_description: str | None
    seed_position_errors: list[dict]
    mean_position_error: float | None
    systematic_offset: tuple[float, float] | None
    tubercles_overlapping_seeds: int
    min_distances_to_seeds: list[float]
    is_regular_grid: bool
    grid_spacing: dict | None
    diagnosis: str
    confidence: str

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "seeds_placed": self.seeds_placed,
            "vlm_tubercles_added": self.vlm_tubercles_added,
            "image_identity": self.image_identity,
            "vlm_reported_seeds": self.vlm_reported_seeds,
            "vlm_seed_positions_reported": self.vlm_seed_positions_reported,
            "vlm_image_description": self.vlm_image_description,
            "seed_position_errors": self.seed_position_errors,
            "mean_position_error": self.mean_position_error,
            "systematic_offset": list(self.systematic_offset) if self.systematic_offset else None,
            "tubercles_overlapping_seeds": self.tubercles_overlapping_seeds,
            "min_distances_to_seeds": self.min_distances_to_seeds,
            "is_regular_grid": self.is_regular_grid,
            "grid_spacing": self.grid_spacing,
            "diagnosis": self.diagnosis,
            "confidence": self.confidence,
        }


def parse_seed_positions_from_response(response_text: str) -> list[dict]:
    """Parse VLM-reported seed positions from response text.

    Looks for patterns like:
    - "Seed 0 (top-left): (~108, ~80)"
    - "Seed 1: (592, 78)"
    - "top-left: approximately (105, 77)"

    Args:
        response_text: VLM response text

    Returns:
        List of dicts with {seed_index, label, reported_x, reported_y}
    """
    positions = []

    # Pattern 1: "Seed N (label): (~X, ~Y)" or "Seed N (label): (X, Y)"
    pattern1 = r"[Ss]eed\s*(\d+)\s*\(([^)]+)\):\s*\(?~?(\d+(?:\.\d+)?)\s*,\s*~?(\d+(?:\.\d+)?)\)?"
    for match in re.finditer(pattern1, response_text):
        positions.append({
            "seed_index": int(match.group(1)),
            "label": match.group(2).strip(),
            "reported_x": float(match.group(3)),
            "reported_y": float(match.group(4)),
        })

    # Pattern 2: "Seed N: (X, Y)" without label
    pattern2 = r"[Ss]eed\s*(\d+):\s*\(?~?(\d+(?:\.\d+)?)\s*,\s*~?(\d+(?:\.\d+)?)\)?"
    for match in re.finditer(pattern2, response_text):
        seed_idx = int(match.group(1))
        # Skip if already found with label
        if not any(p["seed_index"] == seed_idx for p in positions):
            positions.append({
                "seed_index": seed_idx,
                "label": f"seed-{seed_idx}",
                "reported_x": float(match.group(2)),
                "reported_y": float(match.group(3)),
            })

    # Pattern 3: "top-left: (X, Y)" or "center: approximately (X, Y)"
    label_patterns = [
        "top-left", "top-right", "bottom-left", "bottom-right", "center",
        "top-center", "bottom-center", "middle-left", "middle-right",
        "north", "south", "east", "west"
    ]
    for label in label_patterns:
        pattern3 = rf"{label}:\s*(?:approximately\s*)?\(?~?(\d+(?:\.\d+)?)\s*,\s*~?(\d+(?:\.\d+)?)\)?"
        match = re.search(pattern3, response_text, re.IGNORECASE)
        if match:
            # Don't add duplicates
            if not any(p["label"].lower() == label.lower() for p in positions):
                positions.append({
                    "seed_index": -1,  # Unknown index
                    "label": label,
                    "reported_x": float(match.group(1)),
                    "reported_y": float(match.group(2)),
                })

    return positions


def parse_image_description_from_response(response_text: str) -> str | None:
    """Extract image content description from VLM response.

    Looks for descriptions of the center region or distinctive features.

    Args:
        response_text: VLM response text

    Returns:
        Extracted description or None
    """
    # Look for text after "center region" or "I observe"
    patterns = [
        r"[Ii]n the center region[^:]*:\s*(.+?)(?:\n\n|\Z)",
        r"[Cc]enter region[^:]*:\s*(.+?)(?:\n\n|\Z)",
        r"I observe[^:]*:\s*(.+?)(?:\n\n|\Z)",
        r"[Dd]istinctive features?[^:]*:\s*(.+?)(?:\n\n|\Z)",
    ]

    for pattern in patterns:
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            description = match.group(1).strip()
            # Clean up: limit to first 500 chars, remove excessive whitespace
            description = " ".join(description.split())[:500]
            if len(description) > 20:  # Minimum meaningful description
                return description

    return None


def calculate_seed_position_errors(
    seeds: list[dict],
    reported_positions: list[dict],
) -> tuple[list[dict], float | None, tuple[float, float] | None]:
    """Calculate position errors between expected and reported seed positions.

    Args:
        seeds: List of seed tubercle dicts with expected positions
        reported_positions: List of VLM-reported positions

    Returns:
        Tuple of (errors_list, mean_error, systematic_offset)
    """
    errors = []

    for seed in seeds:
        debug_info = seed.get("_debug", {})
        expected_x = debug_info.get("expected_x", seed.get("centroid_x", 0))
        expected_y = debug_info.get("expected_y", seed.get("centroid_y", 0))
        seed_index = debug_info.get("seed_index", -1)
        seed_label = debug_info.get("description", "")

        # Find matching reported position
        reported = None
        for rp in reported_positions:
            if rp["seed_index"] == seed_index:
                reported = rp
                break
            if rp["label"].lower() == seed_label.lower():
                reported = rp
                break

        if reported:
            dx = reported["reported_x"] - expected_x
            dy = reported["reported_y"] - expected_y
            distance = math.sqrt(dx * dx + dy * dy)
            errors.append({
                "seed_index": seed_index,
                "label": seed_label,
                "expected": [expected_x, expected_y],
                "reported": [reported["reported_x"], reported["reported_y"]],
                "dx": dx,
                "dy": dy,
                "error_px": distance,
            })

    if not errors:
        return [], None, None

    # Calculate mean error
    mean_error = sum(e["error_px"] for e in errors) / len(errors)

    # Check for systematic offset (if all errors are similar direction)
    mean_dx = sum(e["dx"] for e in errors) / len(errors)
    mean_dy = sum(e["dy"] for e in errors) / len(errors)

    # Systematic offset if mean dx/dy is significant (> 5px) and
    # individual errors are clustered around the mean
    dx_variance = sum((e["dx"] - mean_dx) ** 2 for e in errors) / len(errors)
    dy_variance = sum((e["dy"] - mean_dy) ** 2 for e in errors) / len(errors)

    systematic_offset = None
    if abs(mean_dx) > 5 or abs(mean_dy) > 5:
        # Check if variance is low (errors are consistent)
        if dx_variance < 100 and dy_variance < 100:  # std < 10px
            systematic_offset = (mean_dx, mean_dy)

    return errors, mean_error, systematic_offset


def detect_seed_overlaps(
    seeds: list[dict],
    vlm_tubercles: list[dict],
    overlap_threshold: float = 30.0,
) -> tuple[int, list[float]]:
    """Detect if VLM-added tubercles overlap with seed positions.

    Args:
        seeds: List of seed tubercle dicts
        vlm_tubercles: List of VLM-added tubercle dicts
        overlap_threshold: Distance in pixels to consider an overlap

    Returns:
        Tuple of (overlap_count, min_distances_list)
    """
    if not seeds or not vlm_tubercles:
        return 0, []

    overlap_count = 0
    min_distances = []

    for vlm_tub in vlm_tubercles:
        vlm_x = vlm_tub.get("centroid_x", 0)
        vlm_y = vlm_tub.get("centroid_y", 0)

        min_dist = float("inf")
        for seed in seeds:
            seed_x = seed.get("centroid_x", 0)
            seed_y = seed.get("centroid_y", 0)
            dist = math.sqrt((vlm_x - seed_x) ** 2 + (vlm_y - seed_y) ** 2)
            min_dist = min(min_dist, dist)

        min_distances.append(min_dist)
        if min_dist < overlap_threshold:
            overlap_count += 1

    return overlap_count, min_distances


def detect_regular_grid_pattern(
    tubercles: list[dict],
    tolerance: float = 0.15,
) -> tuple[bool, dict | None]:
    """Detect if tubercles form a regular grid pattern.

    A regular grid has consistent horizontal and vertical spacing.

    Args:
        tubercles: List of tubercle dicts
        tolerance: Relative tolerance for spacing consistency (default 15%)

    Returns:
        Tuple of (is_regular_grid, grid_info_dict)
    """
    if len(tubercles) < 9:  # Need at least 3x3 for meaningful grid detection
        return False, None

    # Extract positions
    positions = [(t.get("centroid_x", 0), t.get("centroid_y", 0)) for t in tubercles]

    # Sort by x, then by y to find rows
    positions_sorted = sorted(positions, key=lambda p: (p[1], p[0]))

    # Try to detect horizontal spacing
    horizontal_spacings = []
    for i in range(len(positions_sorted) - 1):
        x1, y1 = positions_sorted[i]
        x2, y2 = positions_sorted[i + 1]
        # Only consider points in similar y position (same row)
        if abs(y2 - y1) < 50:  # Same row threshold
            dx = abs(x2 - x1)
            if dx > 20:  # Minimum spacing
                horizontal_spacings.append(dx)

    # Sort by y, then by x to find columns
    positions_sorted_y = sorted(positions, key=lambda p: (p[0], p[1]))

    # Try to detect vertical spacing
    vertical_spacings = []
    for i in range(len(positions_sorted_y) - 1):
        x1, y1 = positions_sorted_y[i]
        x2, y2 = positions_sorted_y[i + 1]
        # Only consider points in similar x position (same column)
        if abs(x2 - x1) < 50:  # Same column threshold
            dy = abs(y2 - y1)
            if dy > 20:  # Minimum spacing
                vertical_spacings.append(dy)

    if not horizontal_spacings or not vertical_spacings:
        return False, None

    # Calculate mean and CV (coefficient of variation)
    def cv(values):
        if not values:
            return float("inf")
        mean = sum(values) / len(values)
        if mean == 0:
            return float("inf")
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = math.sqrt(variance)
        return std / mean

    h_mean = sum(horizontal_spacings) / len(horizontal_spacings)
    v_mean = sum(vertical_spacings) / len(vertical_spacings)
    h_cv = cv(horizontal_spacings)
    v_cv = cv(vertical_spacings)

    # Regular grid if both horizontal and vertical spacing have low CV
    is_regular = h_cv < tolerance and v_cv < tolerance

    grid_info = {
        "horizontal_spacing_mean": round(h_mean, 1),
        "horizontal_spacing_cv": round(h_cv, 3),
        "vertical_spacing_mean": round(v_mean, 1),
        "vertical_spacing_cv": round(v_cv, 3),
        "n_horizontal_samples": len(horizontal_spacings),
        "n_vertical_samples": len(vertical_spacings),
    }

    return is_regular, grid_info


def generate_diagnosis(
    seeds_placed: int,
    vlm_tubercles_added: int,
    vlm_reported_seeds: bool,
    mean_position_error: float | None,
    systematic_offset: tuple[float, float] | None,
    tubercles_overlapping_seeds: int,
    is_regular_grid: bool,
    image_identity_matches: bool | None,
) -> tuple[str, str]:
    """Generate a diagnosis based on analysis results.

    Args:
        seeds_placed: Number of seeds placed
        vlm_tubercles_added: Number of tubercles added by VLM
        vlm_reported_seeds: Whether VLM reported seeing seeds
        mean_position_error: Mean position error in pixels
        systematic_offset: Systematic (dx, dy) offset if detected
        tubercles_overlapping_seeds: Count of tubercles overlapping seeds
        is_regular_grid: Whether VLM pattern is a regular grid
        image_identity_matches: Whether image identity matches comparison

    Returns:
        Tuple of (diagnosis_text, confidence_level)
    """
    diagnoses = []
    confidence = "high"

    # Check image identity first
    if image_identity_matches is False:
        diagnoses.append("DIFFERENT IMAGES: Hash mismatch indicates different source images were used")
        return "; ".join(diagnoses), "high"

    # Check if VLM reported seeds
    if not vlm_reported_seeds:
        diagnoses.append("VLM did not report seed positions (may be ignoring prompt instructions)")
        confidence = "medium"

    # Check position accuracy
    if mean_position_error is not None:
        if mean_position_error < 10:
            diagnoses.append(f"Coordinate system working correctly (mean error: {mean_position_error:.1f}px)")
        elif mean_position_error < 30:
            diagnoses.append(f"Minor coordinate inaccuracy (mean error: {mean_position_error:.1f}px)")
            confidence = "medium"
        else:
            diagnoses.append(f"Significant coordinate errors (mean error: {mean_position_error:.1f}px)")
            confidence = "medium"

    # Check systematic offset
    if systematic_offset:
        dx, dy = systematic_offset
        diagnoses.append(f"Systematic coordinate offset detected: ({dx:+.1f}, {dy:+.1f})px")
        confidence = "high"

    # Check seed overlaps
    if tubercles_overlapping_seeds > 0:
        overlap_pct = (tubercles_overlapping_seeds / max(vlm_tubercles_added, 1)) * 100
        if overlap_pct > 20:
            diagnoses.append(f"VLM adding tubercles on top of seeds ({tubercles_overlapping_seeds} overlaps) - not perceiving overlay")
            confidence = "high"
        else:
            diagnoses.append(f"Some tubercles near seeds ({tubercles_overlapping_seeds} within 30px)")

    # Check regular grid pattern (indicates hallucination)
    if is_regular_grid and vlm_tubercles_added > 15:
        diagnoses.append("VLM generating idealized regular grid pattern rather than detecting actual features")
        confidence = "high"

    # Default diagnosis
    if not diagnoses:
        if vlm_tubercles_added == 0:
            diagnoses.append("No tubercles added by VLM")
        else:
            diagnoses.append("VLM behavior appears normal")
            if image_identity_matches is True:
                diagnoses.append("Image identity confirmed (hash match)")

    return "; ".join(diagnoses), confidence


def analyze_debug_seed_results(
    seeds: list[dict],
    vlm_tubercles: list[dict],
    vlm_responses: list[str],
    image_identity: dict,
    comparison_identity: dict | None = None,
) -> dict:
    """Analyze VLM behavior relative to debug seeds.

    Args:
        seeds: List of seed tubercle dicts (source: "debug_seed")
        vlm_tubercles: List of tubercles added by VLM (non-seed tubercles)
        vlm_responses: List of VLM response texts from the session
        image_identity: Current image identity dict
        comparison_identity: Optional identity from another annotation set

    Returns:
        Analysis results dict
    """
    # Combine all VLM responses
    combined_responses = "\n\n".join(vlm_responses) if vlm_responses else ""

    # Parse VLM-reported seed positions
    reported_positions = parse_seed_positions_from_response(combined_responses)
    vlm_reported_seeds = len(reported_positions) > 0

    # Parse image description
    vlm_image_description = parse_image_description_from_response(combined_responses)

    # Calculate position errors
    seed_errors, mean_error, systematic_offset = calculate_seed_position_errors(
        seeds, reported_positions
    )

    # Detect overlaps
    overlap_count, min_distances = detect_seed_overlaps(seeds, vlm_tubercles)

    # Detect regular grid pattern
    is_regular_grid, grid_info = detect_regular_grid_pattern(vlm_tubercles)

    # Image identity comparison
    image_identity_info = {
        "hash": image_identity.get("hash_sha256"),
        "path": image_identity.get("path"),
        "dimensions": image_identity.get("dimensions"),
        "matches_comparison": None,
        "hash_mismatch": False,
        "dimension_mismatch": False,
    }

    if comparison_identity:
        image_identity_info["matches_comparison"] = (
            image_identity.get("hash_sha256") == comparison_identity.get("hash_sha256")
        )
        image_identity_info["hash_mismatch"] = not image_identity_info["matches_comparison"]
        image_identity_info["dimension_mismatch"] = (
            image_identity.get("dimensions") != comparison_identity.get("dimensions")
        )

    # Generate diagnosis
    diagnosis, confidence = generate_diagnosis(
        seeds_placed=len(seeds),
        vlm_tubercles_added=len(vlm_tubercles),
        vlm_reported_seeds=vlm_reported_seeds,
        mean_position_error=mean_error,
        systematic_offset=systematic_offset,
        tubercles_overlapping_seeds=overlap_count,
        is_regular_grid=is_regular_grid,
        image_identity_matches=image_identity_info.get("matches_comparison"),
    )

    # Build result
    result = AnalysisResult(
        seeds_placed=len(seeds),
        vlm_tubercles_added=len(vlm_tubercles),
        image_identity=image_identity_info,
        vlm_reported_seeds=vlm_reported_seeds,
        vlm_seed_positions_reported=reported_positions,
        vlm_image_description=vlm_image_description,
        seed_position_errors=seed_errors,
        mean_position_error=round(mean_error, 2) if mean_error else None,
        systematic_offset=systematic_offset,
        tubercles_overlapping_seeds=overlap_count,
        min_distances_to_seeds=[round(d, 1) for d in min_distances[:10]],  # Limit to first 10
        is_regular_grid=is_regular_grid,
        grid_spacing=grid_info,
        diagnosis=diagnosis,
        confidence=confidence,
    )

    return result.to_dict()


def format_analysis_report(analysis: dict) -> str:
    """Format analysis results as a human-readable report.

    Args:
        analysis: Analysis results dict from analyze_debug_seed_results()

    Returns:
        Formatted report string
    """
    lines = []
    lines.append("=" * 54)
    lines.append("  DEBUG SEED ANALYSIS REPORT")
    lines.append("=" * 54)

    # Image identity
    identity = analysis.get("image_identity", {})
    lines.append("")
    lines.append("  IMAGE IDENTITY VERIFICATION")
    lines.append("-" * 54)
    if identity.get("path"):
        # Truncate path for display
        path = identity["path"]
        if len(path) > 45:
            path = "..." + path[-42:]
        lines.append(f"  Path: {path}")
    if identity.get("hash"):
        lines.append(f"  Hash: {identity['hash'][:16]}... (SHA-256)")
    if identity.get("dimensions"):
        dims = identity["dimensions"]
        lines.append(f"  Dimensions: {dims[0]} x {dims[1]} pixels")

    if identity.get("matches_comparison") is not None:
        match_str = "YES" if identity["matches_comparison"] else "NO"
        symbol = "+" if identity["matches_comparison"] else "X"
        lines.append(f"  Comparison hash match: {match_str} {symbol}")

    # Seed position accuracy
    lines.append("")
    lines.append("  SEED POSITION ACCURACY")
    lines.append("-" * 54)
    lines.append(f"  Seeds placed: {analysis.get('seeds_placed', 0)}")
    lines.append(f"  VLM reported seeds: {'Yes' if analysis.get('vlm_reported_seeds') else 'No'}")

    errors = analysis.get("seed_position_errors", [])
    if errors:
        for err in errors[:5]:  # Show first 5
            lines.append(
                f"  Seed {err['seed_index']} ({err['label']}): "
                f"Expected {err['expected']}, Reported {err['reported']}, "
                f"Error: {err['error_px']:.1f}px"
            )
        if len(errors) > 5:
            lines.append(f"  ... and {len(errors) - 5} more")

    if analysis.get("mean_position_error") is not None:
        lines.append(f"  Mean error: {analysis['mean_position_error']:.1f} px")

    offset = analysis.get("systematic_offset")
    if offset:
        lines.append(f"  Systematic offset: ({offset[0]:+.1f}, {offset[1]:+.1f}) px")

    # Collision analysis
    lines.append("")
    lines.append("  COLLISION ANALYSIS")
    lines.append("-" * 54)
    lines.append(f"  Tubercles added by VLM: {analysis.get('vlm_tubercles_added', 0)}")
    lines.append(f"  Overlapping seeds (< 30px): {analysis.get('tubercles_overlapping_seeds', 0)}")

    min_dists = analysis.get("min_distances_to_seeds", [])
    if min_dists:
        lines.append(f"  Min distance to seed: {min(min_dists):.1f} px")

    # Pattern analysis
    lines.append("")
    lines.append("  PATTERN ANALYSIS")
    lines.append("-" * 54)
    is_grid = analysis.get("is_regular_grid", False)
    lines.append(f"  Regular grid detected: {'YES' if is_grid else 'No'}")

    grid_info = analysis.get("grid_spacing")
    if grid_info:
        lines.append(f"  Horizontal spacing: ~{grid_info['horizontal_spacing_mean']:.0f} px (CV: {grid_info['horizontal_spacing_cv']:.2f})")
        lines.append(f"  Vertical spacing: ~{grid_info['vertical_spacing_mean']:.0f} px (CV: {grid_info['vertical_spacing_cv']:.2f})")

    # Image description
    description = analysis.get("vlm_image_description")
    if description:
        lines.append("")
        lines.append("  VLM IMAGE DESCRIPTION")
        lines.append("-" * 54)
        # Word wrap description
        words = description.split()
        line = "  "
        for word in words:
            if len(line) + len(word) > 52:
                lines.append(line)
                line = "  " + word
            else:
                line += " " + word if line != "  " else word
        if line.strip():
            lines.append(line)

    # Diagnosis
    lines.append("")
    lines.append("  DIAGNOSIS")
    lines.append("-" * 54)
    diagnosis = analysis.get("diagnosis", "No diagnosis")
    confidence = analysis.get("confidence", "unknown")
    lines.append(f"  Confidence: {confidence.upper()}")
    lines.append("")
    # Word wrap diagnosis
    words = diagnosis.split()
    line = "  "
    for word in words:
        if len(line) + len(word) > 52:
            lines.append(line)
            line = "  " + word
        else:
            line += " " + word if line != "  " else word
    if line.strip():
        lines.append(line)

    lines.append("")
    lines.append("=" * 54)

    return "\n".join(lines)
