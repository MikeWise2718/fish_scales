"""Lattice-aware tubercle detection using hexagonal lattice model.

This module implements a seed-and-propagate algorithm that leverages the
roughly hexagonal arrangement of tubercles on ganoid fish scales to improve
detection accuracy compared to local-only blob detection.

Algorithm overview:
1. Seed Detection: Find high-confidence tubercles with strict thresholds
2. Lattice Estimation: Fit hexagonal lattice model to seeds
3. Propagation: Use lattice to predict and validate additional tubercles
4. Refinement: Prune outliers and fill gaps based on lattice consistency
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Set
import heapq

import numpy as np
from scipy.spatial import Delaunay, cKDTree
from scipy import ndimage
from skimage.feature import blob_log, peak_local_max

from ..models import CalibrationData, Tubercle


@dataclass
class LatticeModel:
    """Represents an estimated hexagonal lattice."""

    v1: np.ndarray  # First basis vector (2D)
    v2: np.ndarray  # Second basis vector (2D)
    origin: np.ndarray  # Reference point for lattice
    spacing: float  # Mean spacing in pixels
    angle: float  # Angle between v1 and v2 (radians)
    regularity: float  # Quality score 0-1 (how well points fit lattice)

    def predict_position(self, i: int, j: int) -> np.ndarray:
        """Get lattice position at indices (i, j) relative to origin."""
        return self.origin + i * self.v1 + j * self.v2

    def nearest_lattice_indices(self, position: np.ndarray) -> Tuple[int, int]:
        """Find nearest lattice indices for a given position."""
        # Solve: position = origin + i*v1 + j*v2
        # Using matrix inverse: [i, j]^T = M^-1 * (position - origin)
        M = np.column_stack([self.v1, self.v2])
        try:
            coeffs = np.linalg.solve(M, position - self.origin)
            return int(round(coeffs[0])), int(round(coeffs[1]))
        except np.linalg.LinAlgError:
            return 0, 0

    def nearest_lattice_position(self, position: np.ndarray) -> np.ndarray:
        """Find nearest ideal lattice position."""
        i, j = self.nearest_lattice_indices(position)
        return self.predict_position(i, j)

    def deviation_from_lattice(self, position: np.ndarray) -> float:
        """Calculate deviation from nearest lattice position (in pixels)."""
        nearest = self.nearest_lattice_position(position)
        return float(np.linalg.norm(position - nearest))

    def get_neighbor_directions(self) -> List[np.ndarray]:
        """Get the 6 hexagonal neighbor direction vectors."""
        return [
            self.v1,
            self.v2,
            self.v1 - self.v2,  # For proper hexagonal neighbors
            -self.v1,
            -self.v2,
            -self.v1 + self.v2,
        ]


@dataclass
class LatticeParams:
    """Parameters for lattice-aware detection."""

    # Seed detection (strict thresholds)
    seed_threshold: float = 0.08
    seed_circularity: float = 0.6
    seed_min_contrast: float = 1.3  # Peak vs surrounding annulus
    min_seeds: int = 5

    # Lattice validation
    min_regularity: float = 0.25  # Lowered - real images have some irregularity
    angle_tolerance_deg: float = 25.0  # Deviation from 60 degrees
    spacing_ratio_tolerance: float = 0.5  # |v1|/|v2| deviation from 1.0

    # Propagation
    search_radius_factor: float = 0.35  # Fraction of lattice spacing
    propagation_threshold: float = 0.03  # More lenient than seeds
    propagation_circularity: float = 0.3
    propagation_min_contrast: float = 1.1
    max_propagation_iterations: int = 500

    # Refinement
    max_lattice_deviation: float = 0.4  # Fraction of spacing
    gap_fill_min_neighbors: int = 4
    gap_fill_threshold: float = 0.02  # Very lenient for gaps


@dataclass
class SeedCandidate:
    """A candidate seed tubercle with quality metrics."""
    position: np.ndarray  # (x, y) position
    sigma: float  # Blob sigma (relates to size)
    intensity: float  # Peak intensity
    contrast_ratio: float  # Local contrast
    circularity: float  # Shape quality
    confidence: float  # Overall confidence score

    def __lt__(self, other):
        """For priority queue ordering (higher confidence first)."""
        return self.confidence > other.confidence


def compute_local_contrast(
    image: np.ndarray,
    position: Tuple[float, float],
    radius: float,
) -> float:
    """
    Compute contrast ratio between peak and surrounding annulus.

    Args:
        image: Grayscale image
        position: (x, y) center position
        radius: Estimated blob radius

    Returns:
        Ratio of center intensity to annulus intensity
    """
    x, y = position
    h, w = image.shape[:2]

    # Define regions
    inner_radius = max(1, radius * 0.7)
    outer_radius = radius * 1.5

    # Create coordinate grids
    y_coords, x_coords = np.ogrid[:h, :w]
    dist_sq = (x_coords - x)**2 + (y_coords - y)**2

    # Masks for inner circle and annulus
    inner_mask = dist_sq <= inner_radius**2
    annulus_mask = (dist_sq > inner_radius**2) & (dist_sq <= outer_radius**2)

    # Calculate mean intensities
    if np.any(inner_mask) and np.any(annulus_mask):
        inner_mean = np.mean(image[inner_mask])
        annulus_mean = np.mean(image[annulus_mask])
        if annulus_mean > 1e-10:
            return inner_mean / annulus_mean

    return 1.0


def compute_circularity_fast(
    image: np.ndarray,
    position: Tuple[float, float],
    radius: float,
) -> float:
    """
    Fast circularity estimate using radial intensity profile.

    Args:
        image: Grayscale image
        position: (x, y) center position
        radius: Estimated blob radius

    Returns:
        Circularity score 0-1 (1 = perfectly circular intensity profile)
    """
    x, y = position
    h, w = image.shape[:2]

    # Sample points around the perimeter
    n_samples = 16
    angles = np.linspace(0, 2 * np.pi, n_samples, endpoint=False)
    sample_radius = radius * 0.8

    intensities = []
    for angle in angles:
        sx = int(round(x + sample_radius * np.cos(angle)))
        sy = int(round(y + sample_radius * np.sin(angle)))
        if 0 <= sx < w and 0 <= sy < h:
            intensities.append(image[sy, sx])

    if len(intensities) < n_samples // 2:
        return 0.0

    # Circularity = 1 - coefficient of variation of perimeter intensities
    intensities = np.array(intensities)
    mean_int = np.mean(intensities)
    if mean_int > 1e-10:
        cv = np.std(intensities) / mean_int
        return max(0, 1 - cv)
    return 0.0


def detect_seeds(
    image: np.ndarray,
    calibration: CalibrationData,
    min_diameter_um: float,
    max_diameter_um: float,
    params: LatticeParams,
) -> List[SeedCandidate]:
    """
    Detect high-confidence seed tubercles.

    Uses strict thresholds to find only the most obvious tubercles
    that will bootstrap the lattice model.

    Args:
        image: Preprocessed grayscale image (float, 0-1)
        calibration: Calibration data for pixel-to-um conversion
        min_diameter_um: Minimum expected diameter
        max_diameter_um: Maximum expected diameter
        params: Detection parameters

    Returns:
        List of SeedCandidate objects sorted by confidence
    """
    # Calculate sigma range from expected diameters
    min_diameter_px = min_diameter_um / calibration.um_per_pixel
    max_diameter_px = max_diameter_um / calibration.um_per_pixel

    min_sigma = min_diameter_px / (2 * np.sqrt(2))
    max_sigma = max_diameter_px / (2 * np.sqrt(2))
    min_sigma = max(1.0, min_sigma)
    max_sigma = max(min_sigma + 1, max_sigma)

    # Detect blobs with strict threshold
    blobs = blob_log(
        image,
        min_sigma=min_sigma,
        max_sigma=max_sigma,
        num_sigma=10,
        threshold=params.seed_threshold,
        overlap=0.5,
    )

    if len(blobs) == 0:
        return []

    seeds = []
    h, w = image.shape[:2]
    edge_margin = int(max_diameter_px)

    for blob in blobs:
        y, x, sigma = blob

        # Skip edge detections
        if x < edge_margin or x > w - edge_margin:
            continue
        if y < edge_margin or y > h - edge_margin:
            continue

        radius = np.sqrt(2) * sigma
        diameter_px = 2 * radius
        diameter_um = diameter_px * calibration.um_per_pixel

        # Size filter
        if diameter_um < min_diameter_um or diameter_um > max_diameter_um:
            continue

        # Quality metrics
        contrast = compute_local_contrast(image, (x, y), radius)
        circularity = compute_circularity_fast(image, (x, y), radius)
        intensity = image[int(y), int(x)]

        # Filter by quality
        if contrast < params.seed_min_contrast:
            continue
        if circularity < params.seed_circularity:
            continue

        # Compute confidence score
        confidence = (
            0.4 * min(contrast / 2.0, 1.0) +
            0.3 * circularity +
            0.3 * intensity
        )

        seeds.append(SeedCandidate(
            position=np.array([x, y]),
            sigma=sigma,
            intensity=intensity,
            contrast_ratio=contrast,
            circularity=circularity,
            confidence=confidence,
        ))

    # Sort by confidence (highest first)
    seeds.sort(key=lambda s: s.confidence, reverse=True)
    return seeds


def estimate_lattice_vectors(
    positions: np.ndarray,
    expected_spacing_px: float,
) -> Tuple[np.ndarray, np.ndarray, float]:
    """
    Estimate lattice basis vectors from a set of positions.

    Uses Delaunay triangulation to find edges, then clusters edge
    vectors by direction to identify the dominant lattice directions.

    Args:
        positions: Array of shape (n, 2) with (x, y) positions
        expected_spacing_px: Expected spacing to filter edges

    Returns:
        Tuple of (v1, v2, regularity_score)
    """
    if len(positions) < 4:
        return None, None, 0.0

    # Build Delaunay triangulation
    try:
        tri = Delaunay(positions)
    except Exception:
        return None, None, 0.0

    # Collect all edge vectors
    edge_vectors = []
    for simplex in tri.simplices:
        for i in range(3):
            for j in range(i + 1, 3):
                p1 = positions[simplex[i]]
                p2 = positions[simplex[j]]
                vec = p2 - p1
                dist = np.linalg.norm(vec)

                # Filter by expected spacing (0.5x to 2x expected)
                if 0.5 * expected_spacing_px < dist < 2.0 * expected_spacing_px:
                    edge_vectors.append(vec)
                    edge_vectors.append(-vec)  # Include both directions

    if len(edge_vectors) < 6:
        return None, None, 0.0

    edge_vectors = np.array(edge_vectors)

    # Convert to angles (0 to pi, since we included both directions)
    angles = np.arctan2(edge_vectors[:, 1], edge_vectors[:, 0])
    angles = np.mod(angles, np.pi)  # Fold to 0-pi range

    # Cluster angles into 3 groups (hexagonal lattice has 3 primary directions)
    # Use histogram-based clustering
    n_bins = 36
    hist, bin_edges = np.histogram(angles, bins=n_bins, range=(0, np.pi))

    # Find peaks in histogram (expect 3 for hexagonal)
    # Smooth histogram first
    hist_smooth = np.convolve(hist, [0.25, 0.5, 0.25], mode='same')

    # Find local maxima
    peaks = []
    for i in range(1, n_bins - 1):
        if hist_smooth[i] > hist_smooth[i-1] and hist_smooth[i] > hist_smooth[i+1]:
            if hist_smooth[i] > np.mean(hist_smooth):
                peak_angle = (bin_edges[i] + bin_edges[i+1]) / 2
                peaks.append((hist_smooth[i], peak_angle))

    if len(peaks) < 2:
        # Fallback: use PCA on edge vectors
        centered = edge_vectors - np.mean(edge_vectors, axis=0)
        try:
            _, _, Vt = np.linalg.svd(centered)
            v1_dir = Vt[0]
            v2_dir = Vt[1]
        except Exception:
            return None, None, 0.0
    else:
        # Sort peaks by strength and take top 2
        peaks.sort(reverse=True)
        angle1 = peaks[0][1]
        angle2 = peaks[1][1] if len(peaks) > 1 else angle1 + np.pi/3

        v1_dir = np.array([np.cos(angle1), np.sin(angle1)])
        v2_dir = np.array([np.cos(angle2), np.sin(angle2)])

    # Estimate spacing from median edge length
    edge_lengths = np.linalg.norm(edge_vectors, axis=1)
    median_spacing = np.median(edge_lengths)

    # Scale direction vectors by median spacing
    v1 = v1_dir * median_spacing
    v2 = v2_dir * median_spacing

    # Compute regularity score
    # For each position, find nearest lattice position and measure deviation
    origin = np.mean(positions, axis=0)
    deviations = []

    for pos in positions:
        # Find nearest lattice point
        M = np.column_stack([v1, v2])
        try:
            coeffs = np.linalg.solve(M, pos - origin)
            i, j = int(round(coeffs[0])), int(round(coeffs[1]))
            nearest = origin + i * v1 + j * v2
            dev = np.linalg.norm(pos - nearest) / median_spacing
            deviations.append(dev)
        except Exception:
            deviations.append(1.0)

    # Regularity = fraction of points within tolerance
    regularity = np.mean(np.array(deviations) < 0.35)

    return v1, v2, float(regularity)


def estimate_lattice(
    seeds: List[SeedCandidate],
    calibration: CalibrationData,
    min_diameter_um: float,
    max_diameter_um: float,
    params: LatticeParams,
) -> Optional[LatticeModel]:
    """
    Estimate hexagonal lattice model from seed positions.

    Args:
        seeds: List of seed candidates
        calibration: Calibration data
        min_diameter_um: Minimum expected diameter
        max_diameter_um: Maximum expected diameter
        params: Lattice parameters

    Returns:
        LatticeModel if valid lattice found, None otherwise
    """
    if len(seeds) < params.min_seeds:
        return None

    # Extract positions
    positions = np.array([s.position for s in seeds])

    # Expected spacing is roughly 1.5-3x the diameter
    mean_diameter_um = (min_diameter_um + max_diameter_um) / 2
    mean_diameter_px = mean_diameter_um / calibration.um_per_pixel
    expected_spacing_px = mean_diameter_px * 2.0

    # Estimate lattice vectors
    v1, v2, regularity = estimate_lattice_vectors(positions, expected_spacing_px)

    if v1 is None or v2 is None:
        return None

    if regularity < params.min_regularity:
        return None

    # Validate lattice geometry
    # Check angle between vectors (should be ~60 degrees for hexagonal)
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    cos_angle = np.clip(cos_angle, -1, 1)
    angle = np.arccos(cos_angle)
    angle_deg = np.degrees(angle)

    # Accept if angle is near 60, 120, or 90 (slightly distorted lattice)
    angle_from_60 = min(abs(angle_deg - 60), abs(angle_deg - 120))
    if angle_from_60 > params.angle_tolerance_deg and abs(angle_deg - 90) > params.angle_tolerance_deg:
        return None

    # Check spacing ratio
    len_v1 = np.linalg.norm(v1)
    len_v2 = np.linalg.norm(v2)
    spacing_ratio = max(len_v1, len_v2) / min(len_v1, len_v2)
    if abs(spacing_ratio - 1.0) > params.spacing_ratio_tolerance:
        return None

    spacing = (len_v1 + len_v2) / 2
    origin = np.mean(positions, axis=0)

    return LatticeModel(
        v1=v1,
        v2=v2,
        origin=origin,
        spacing=spacing,
        angle=angle,
        regularity=regularity,
    )


def validate_candidate_at_position(
    image: np.ndarray,
    predicted_pos: np.ndarray,
    expected_radius: float,
    search_radius: float,
    params: LatticeParams,
) -> Optional[Tuple[np.ndarray, float, float, float]]:
    """
    Check if there's a valid tubercle at or near the predicted position.

    Args:
        image: Preprocessed image
        predicted_pos: Expected (x, y) position
        expected_radius: Expected blob radius in pixels
        search_radius: How far to search from predicted position
        params: Detection parameters

    Returns:
        Tuple of (refined_position, sigma, contrast, circularity) if found, None otherwise
    """
    h, w = image.shape[:2]
    x, y = predicted_pos

    # Check bounds
    margin = int(search_radius + expected_radius)
    if x < margin or x > w - margin or y < margin or y > h - margin:
        return None

    # Extract search region
    x_min = int(max(0, x - search_radius))
    x_max = int(min(w, x + search_radius + 1))
    y_min = int(max(0, y - search_radius))
    y_max = int(min(h, y + search_radius + 1))

    region = image[y_min:y_max, x_min:x_max]

    if region.size == 0:
        return None

    # Find local maximum in search region
    local_max_coords = peak_local_max(
        region,
        min_distance=int(expected_radius * 0.5),
        threshold_abs=params.propagation_threshold,
        num_peaks=3,
    )

    if len(local_max_coords) == 0:
        # Fallback: use maximum intensity point
        max_idx = np.unravel_index(np.argmax(region), region.shape)
        local_max_coords = np.array([max_idx])

    # Evaluate each local maximum
    best_candidate = None
    best_score = -1

    for local_yx in local_max_coords:
        local_y, local_x = local_yx
        global_x = x_min + local_x
        global_y = y_min + local_y

        # Check distance from predicted position
        dist = np.sqrt((global_x - x)**2 + (global_y - y)**2)
        if dist > search_radius:
            continue

        # Compute quality metrics
        contrast = compute_local_contrast(image, (global_x, global_y), expected_radius)
        circularity = compute_circularity_fast(image, (global_x, global_y), expected_radius)
        intensity = image[global_y, global_x]

        # Apply more lenient thresholds for propagation
        if contrast < params.propagation_min_contrast:
            continue
        if circularity < params.propagation_circularity:
            continue

        # Score based on quality and distance from prediction
        distance_penalty = dist / search_radius
        score = (
            0.3 * min(contrast / 1.5, 1.0) +
            0.2 * circularity +
            0.2 * intensity +
            0.3 * (1 - distance_penalty)
        )

        if score > best_score:
            best_score = score
            best_candidate = (
                np.array([global_x, global_y]),
                expected_radius / np.sqrt(2),  # Convert back to sigma
                contrast,
                circularity,
            )

    return best_candidate


def propagate_detections(
    seeds: List[SeedCandidate],
    image: np.ndarray,
    lattice: LatticeModel,
    calibration: CalibrationData,
    min_diameter_um: float,
    max_diameter_um: float,
    params: LatticeParams,
) -> List[SeedCandidate]:
    """
    Propagate from seeds using lattice model to find additional tubercles.

    Uses a priority queue to process predictions in order of confidence,
    expanding outward from confirmed detections.

    Args:
        seeds: Initial seed detections
        image: Preprocessed image
        lattice: Estimated lattice model
        calibration: Calibration data
        min_diameter_um: Minimum expected diameter
        max_diameter_um: Maximum expected diameter
        params: Detection parameters

    Returns:
        List of all confirmed detections (seeds + propagated)
    """
    h, w = image.shape[:2]

    # Expected radius
    mean_diameter_um = (min_diameter_um + max_diameter_um) / 2
    expected_radius = (mean_diameter_um / calibration.um_per_pixel) / 2

    search_radius = lattice.spacing * params.search_radius_factor
    min_separation = expected_radius * 1.5

    # Initialize with seeds
    confirmed = list(seeds)
    confirmed_positions = {tuple(s.position) for s in seeds}

    # Track processed positions to avoid re-checking
    processed_positions: Set[Tuple[int, int]] = set()
    for seed in seeds:
        grid_pos = (int(seed.position[0] / min_separation),
                    int(seed.position[1] / min_separation))
        processed_positions.add(grid_pos)

    # Priority queue of positions to check
    # (negative confidence for min-heap, position, source)
    queue = []

    # Add initial predictions from seeds
    neighbor_dirs = lattice.get_neighbor_directions()
    for seed in seeds:
        for direction in neighbor_dirs:
            pred_pos = seed.position + direction
            # Check bounds
            if 0 < pred_pos[0] < w and 0 < pred_pos[1] < h:
                heapq.heappush(queue, (-seed.confidence, tuple(pred_pos)))

    iterations = 0
    while queue and iterations < params.max_propagation_iterations:
        iterations += 1

        neg_conf, pred_pos_tuple = heapq.heappop(queue)
        pred_pos = np.array(pred_pos_tuple)

        # Check if already processed (using grid)
        grid_pos = (int(pred_pos[0] / min_separation),
                    int(pred_pos[1] / min_separation))
        if grid_pos in processed_positions:
            continue
        processed_positions.add(grid_pos)

        # Check if too close to existing detection
        too_close = False
        for conf in confirmed:
            if np.linalg.norm(pred_pos - conf.position) < min_separation:
                too_close = True
                break
        if too_close:
            continue

        # Validate candidate at this position
        result = validate_candidate_at_position(
            image, pred_pos, expected_radius, search_radius, params
        )

        if result is not None:
            refined_pos, sigma, contrast, circularity = result

            # Double-check not too close to existing
            too_close = False
            for conf in confirmed:
                if np.linalg.norm(refined_pos - conf.position) < min_separation:
                    too_close = True
                    break
            if too_close:
                continue

            # Compute confidence
            intensity = image[int(refined_pos[1]), int(refined_pos[0])]
            confidence = (
                0.3 * min(contrast / 1.5, 1.0) +
                0.25 * circularity +
                0.25 * intensity +
                0.2 * (1 - lattice.deviation_from_lattice(refined_pos) / lattice.spacing)
            )

            new_detection = SeedCandidate(
                position=refined_pos,
                sigma=sigma,
                intensity=intensity,
                contrast_ratio=contrast,
                circularity=circularity,
                confidence=confidence,
            )

            confirmed.append(new_detection)
            confirmed_positions.add(tuple(refined_pos))

            # Add predictions for neighbors of this new detection
            for direction in neighbor_dirs:
                new_pred_pos = refined_pos + direction
                if 0 < new_pred_pos[0] < w and 0 < new_pred_pos[1] < h:
                    new_grid = (int(new_pred_pos[0] / min_separation),
                               int(new_pred_pos[1] / min_separation))
                    if new_grid not in processed_positions:
                        heapq.heappush(queue, (-confidence, tuple(new_pred_pos)))

    return confirmed


def refine_detections(
    detections: List[SeedCandidate],
    lattice: LatticeModel,
    image: np.ndarray,
    calibration: CalibrationData,
    min_diameter_um: float,
    max_diameter_um: float,
    params: LatticeParams,
) -> List[SeedCandidate]:
    """
    Refine detections by pruning outliers and filling gaps.

    Args:
        detections: Current list of detections
        lattice: Lattice model
        image: Preprocessed image
        calibration: Calibration data
        min_diameter_um: Minimum expected diameter
        max_diameter_um: Maximum expected diameter
        params: Detection parameters

    Returns:
        Refined list of detections
    """
    if len(detections) < 4:
        return detections

    # Re-estimate lattice with all detections for better model
    positions = np.array([d.position for d in detections])
    v1, v2, regularity = estimate_lattice_vectors(positions, lattice.spacing)

    if v1 is not None and v2 is not None and regularity > params.min_regularity:
        refined_lattice = LatticeModel(
            v1=v1,
            v2=v2,
            origin=np.mean(positions, axis=0),
            spacing=(np.linalg.norm(v1) + np.linalg.norm(v2)) / 2,
            angle=np.arccos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)), -1, 1)),
            regularity=regularity,
        )
    else:
        refined_lattice = lattice

    # Prune outliers
    max_dev = params.max_lattice_deviation * refined_lattice.spacing
    pruned = []
    for det in detections:
        deviation = refined_lattice.deviation_from_lattice(det.position)
        if deviation <= max_dev:
            pruned.append(det)

    # Fill gaps
    # Find positions where we expect tubercles but don't have them
    if len(pruned) > 0:
        positions = np.array([d.position for d in pruned])
        tree = cKDTree(positions)

        mean_diameter_um = (min_diameter_um + max_diameter_um) / 2
        expected_radius = (mean_diameter_um / calibration.um_per_pixel) / 2
        search_radius = refined_lattice.spacing * params.search_radius_factor
        min_separation = expected_radius * 1.5

        h, w = image.shape[:2]
        neighbor_dirs = refined_lattice.get_neighbor_directions()

        gaps_to_check = []
        for det in pruned:
            for direction in neighbor_dirs:
                gap_pos = det.position + direction

                # Check if within image
                if not (0 < gap_pos[0] < w and 0 < gap_pos[1] < h):
                    continue

                # Check if there's already a detection nearby
                dist, _ = tree.query(gap_pos)
                if dist < min_separation:
                    continue

                # Count confirmed neighbors
                dists, indices = tree.query(gap_pos, k=min(6, len(positions)))
                n_neighbors = np.sum(dists < refined_lattice.spacing * 1.5)

                if n_neighbors >= params.gap_fill_min_neighbors:
                    gaps_to_check.append(gap_pos)

        # Try to fill gaps with very lenient thresholds
        gap_params = LatticeParams(
            propagation_threshold=params.gap_fill_threshold,
            propagation_min_contrast=1.05,
            propagation_circularity=0.2,
        )

        for gap_pos in gaps_to_check:
            result = validate_candidate_at_position(
                image, gap_pos, expected_radius, search_radius, gap_params
            )

            if result is not None:
                refined_pos, sigma, contrast, circularity = result

                # Check not too close to existing
                dist, _ = tree.query(refined_pos)
                if dist >= min_separation:
                    intensity = image[int(refined_pos[1]), int(refined_pos[0])]
                    confidence = 0.3 * min(contrast / 1.5, 1.0) + 0.3 * circularity + 0.4 * intensity

                    new_det = SeedCandidate(
                        position=refined_pos,
                        sigma=sigma,
                        intensity=intensity,
                        contrast_ratio=contrast,
                        circularity=circularity,
                        confidence=confidence,
                    )
                    pruned.append(new_det)

                    # Update tree for subsequent gap checks
                    positions = np.array([d.position for d in pruned])
                    tree = cKDTree(positions)

    return pruned


def candidates_to_tubercles(
    candidates: List[SeedCandidate],
    calibration: CalibrationData,
) -> List[Tubercle]:
    """
    Convert SeedCandidate objects to Tubercle objects.

    Args:
        candidates: List of validated candidates
        calibration: Calibration data

    Returns:
        List of Tubercle objects
    """
    tubercles = []

    for i, cand in enumerate(candidates):
        radius_px = np.sqrt(2) * cand.sigma
        diameter_px = 2 * radius_px
        diameter_um = diameter_px * calibration.um_per_pixel
        area_px = np.pi * radius_px ** 2

        tubercle = Tubercle(
            id=i + 1,
            centroid=(float(cand.position[0]), float(cand.position[1])),
            diameter_px=float(diameter_px),
            diameter_um=float(diameter_um),
            area_px=float(area_px),
            circularity=float(cand.circularity),
        )
        tubercles.append(tubercle)

    return tubercles


def detect_tubercles_lattice(
    image: np.ndarray,
    calibration: CalibrationData,
    min_diameter_um: float = 2.0,
    max_diameter_um: float = 10.0,
    params: Optional[LatticeParams] = None,
    fallback_to_log: bool = True,
) -> Tuple[List[Tubercle], Optional[LatticeModel], dict]:
    """
    Detect tubercles using lattice-aware algorithm.

    This is the main entry point for lattice-based detection.

    Args:
        image: Preprocessed grayscale image (float, 0-1)
        calibration: Calibration data for pixel-to-um conversion
        min_diameter_um: Minimum expected tubercle diameter
        max_diameter_um: Maximum expected tubercle diameter
        params: Detection parameters (uses defaults if None)
        fallback_to_log: If True, fall back to standard LoG if lattice fails

    Returns:
        Tuple of (tubercles, lattice_model, info_dict)
        lattice_model is None if lattice estimation failed
        info_dict contains diagnostic information
    """
    if params is None:
        params = LatticeParams()

    info = {
        "method": "lattice",
        "phases_completed": [],
        "fallback_used": False,
    }

    # Phase 1: Seed detection
    seeds = detect_seeds(
        image, calibration, min_diameter_um, max_diameter_um, params
    )
    info["n_seeds"] = len(seeds)
    info["phases_completed"].append("seed_detection")

    if len(seeds) < params.min_seeds:
        info["lattice_failed_reason"] = f"insufficient seeds ({len(seeds)} < {params.min_seeds})"
        if fallback_to_log:
            info["fallback_used"] = True
            # Import here to avoid circular import
            from .detection import detect_tubercles as detect_tubercles_log
            tubercles = detect_tubercles_log(
                image, calibration,
                min_diameter_um=min_diameter_um,
                max_diameter_um=max_diameter_um,
                threshold=0.05,
                min_circularity=0.5,
            )
            return tubercles, None, info
        return [], None, info

    # Phase 2: Lattice estimation
    lattice = estimate_lattice(
        seeds, calibration, min_diameter_um, max_diameter_um, params
    )

    if lattice is None:
        info["lattice_failed_reason"] = "lattice estimation failed (irregular pattern?)"
        if fallback_to_log:
            info["fallback_used"] = True
            from .detection import detect_tubercles as detect_tubercles_log
            tubercles = detect_tubercles_log(
                image, calibration,
                min_diameter_um=min_diameter_um,
                max_diameter_um=max_diameter_um,
                threshold=0.05,
                min_circularity=0.5,
            )
            return tubercles, None, info
        return candidates_to_tubercles(seeds, calibration), None, info

    info["lattice_spacing_px"] = lattice.spacing
    info["lattice_spacing_um"] = lattice.spacing * calibration.um_per_pixel
    info["lattice_angle_deg"] = np.degrees(lattice.angle)
    info["lattice_regularity"] = lattice.regularity
    info["phases_completed"].append("lattice_estimation")

    # Phase 3: Propagation
    propagated = propagate_detections(
        seeds, image, lattice, calibration, min_diameter_um, max_diameter_um, params
    )
    info["n_after_propagation"] = len(propagated)
    info["phases_completed"].append("propagation")

    # Phase 4: Refinement
    refined = refine_detections(
        propagated, lattice, image, calibration, min_diameter_um, max_diameter_um, params
    )
    info["n_after_refinement"] = len(refined)
    info["phases_completed"].append("refinement")

    # Convert to Tubercle objects
    tubercles = candidates_to_tubercles(refined, calibration)

    return tubercles, lattice, info
