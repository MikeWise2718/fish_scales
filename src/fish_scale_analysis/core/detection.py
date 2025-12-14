"""Tubercle detection using blob detection algorithms."""

from typing import List, Optional, Tuple

import numpy as np
from scipy import ndimage
from skimage import measure, filters, morphology, segmentation
from skimage.feature import blob_log, blob_dog

from ..models import CalibrationData, Tubercle


def detect_blobs_log(
    image: np.ndarray,
    min_sigma: float = 2.0,
    max_sigma: float = 15.0,
    num_sigma: int = 10,
    threshold: float = 0.1,
    overlap: float = 0.5,
) -> np.ndarray:
    """
    Detect blobs using Laplacian of Gaussian (LoG) method.

    LoG is excellent for detecting bright circular spots on dark background.

    Args:
        image: Preprocessed grayscale image (float, 0-1)
        min_sigma: Minimum sigma for LoG (relates to smallest blob size)
        max_sigma: Maximum sigma for LoG (relates to largest blob size)
        num_sigma: Number of sigma values to try
        threshold: Detection threshold (lower = more sensitive)
        overlap: Maximum overlap between blobs (0-1)

    Returns:
        Array of shape (n, 3) with columns [y, x, sigma]
        Blob radius ≈ sqrt(2) * sigma
    """
    blobs = blob_log(
        image,
        min_sigma=min_sigma,
        max_sigma=max_sigma,
        num_sigma=num_sigma,
        threshold=threshold,
        overlap=overlap,
    )
    return blobs


def detect_blobs_dog(
    image: np.ndarray,
    min_sigma: float = 2.0,
    max_sigma: float = 15.0,
    sigma_ratio: float = 1.6,
    threshold: float = 0.1,
    overlap: float = 0.5,
) -> np.ndarray:
    """
    Detect blobs using Difference of Gaussian (DoG) method.

    DoG is faster than LoG but slightly less accurate.

    Args:
        image: Preprocessed grayscale image
        min_sigma: Minimum sigma
        max_sigma: Maximum sigma
        sigma_ratio: Ratio between successive sigma values
        threshold: Detection threshold
        overlap: Maximum overlap between blobs

    Returns:
        Array of shape (n, 3) with columns [y, x, sigma]
    """
    blobs = blob_dog(
        image,
        min_sigma=min_sigma,
        max_sigma=max_sigma,
        sigma_ratio=sigma_ratio,
        threshold=threshold,
        overlap=overlap,
    )
    return blobs


def calculate_circularity(
    image: np.ndarray,
    center: Tuple[float, float],
    radius: float,
) -> float:
    """
    Calculate circularity of a detected blob region.

    Circularity = 4π × area / perimeter²
    Perfect circle = 1.0

    Args:
        image: Binary or grayscale image
        center: (y, x) center of blob
        radius: Estimated radius of blob

    Returns:
        Circularity value (0-1)
    """
    y, x = center
    h, w = image.shape[:2]

    # Create a mask around the blob
    margin = int(radius * 1.5)
    y_min = max(0, int(y - margin))
    y_max = min(h, int(y + margin + 1))
    x_min = max(0, int(x - margin))
    x_max = min(w, int(x + margin + 1))

    if y_max - y_min < 3 or x_max - x_min < 3:
        return 0.0

    # Extract region
    region = image[y_min:y_max, x_min:x_max]

    # Threshold to get binary mask
    thresh = np.mean(region)
    binary = region > thresh

    # Find contours
    contours = measure.find_contours(binary.astype(float), 0.5)

    if not contours:
        return 0.0

    # Use largest contour
    contour = max(contours, key=len)

    if len(contour) < 5:
        return 0.0

    # Calculate area and perimeter
    # Using the shoelace formula for area
    area = 0.5 * np.abs(
        np.dot(contour[:, 0], np.roll(contour[:, 1], 1))
        - np.dot(contour[:, 1], np.roll(contour[:, 0], 1))
    )

    # Perimeter as sum of distances between consecutive points
    diffs = np.diff(contour, axis=0, append=contour[:1])
    perimeter = np.sum(np.sqrt(np.sum(diffs**2, axis=1)))

    if perimeter < 1e-10:
        return 0.0

    circularity = 4 * np.pi * area / (perimeter**2)
    return min(1.0, circularity)


def fit_ellipse_to_blob(
    image: np.ndarray,
    center: Tuple[float, float],
    radius: float,
    max_eccentricity: float = 0.95,
) -> Optional[dict]:
    """
    Fit an ellipse to a detected blob region.

    Uses regionprops to fit an ellipse to the thresholded region
    around the blob center. Uses conservative thresholding to capture
    only the bright tubercle core, not surrounding halos.

    Args:
        image: Grayscale image (float, 0-1)
        center: (y, x) center of blob
        radius: Estimated radius of blob from LoG
        max_eccentricity: Maximum allowed eccentricity (0=circle, 1=line)

    Returns:
        Dictionary with ellipse parameters or None if fitting fails:
        - major_axis: length of major axis in pixels
        - minor_axis: length of minor axis in pixels
        - orientation: angle of major axis in radians
        - eccentricity: ellipse eccentricity
        - centroid: (x, y) refined centroid
        - area: area in pixels
        - equivalent_diameter: diameter of circle with same area
    """
    y, x = center
    h, w = image.shape[:2]

    # Extract region around blob (tighter margin to avoid neighbors)
    margin = int(radius * 1.5)
    y_min = max(0, int(y - margin))
    y_max = min(h, int(y + margin + 1))
    x_min = max(0, int(x - margin))
    x_max = min(w, int(x + margin + 1))

    if y_max - y_min < 5 or x_max - x_min < 5:
        return None

    # Extract region
    region = image[y_min:y_max, x_min:x_max]

    # Use a higher threshold to capture just the bright core
    # Try multiple thresholding strategies and pick the best

    # Strategy 1: High percentile (captures bright core)
    thresh_percentile = np.percentile(region, 75)

    # Strategy 2: Otsu (may be too permissive)
    try:
        thresh_otsu = filters.threshold_otsu(region)
    except ValueError:
        thresh_otsu = np.mean(region)

    # Use the higher threshold to be more conservative
    thresh_val = max(thresh_percentile, thresh_otsu)

    # Additional boost: use mean + 0.5*std as minimum threshold
    thresh_robust = np.mean(region) + 0.5 * np.std(region)
    thresh_val = max(thresh_val, thresh_robust)

    binary = region > thresh_val

    # Apply circular mask centered on expected position to avoid neighbors
    cy_local, cx_local = y - y_min, x - x_min
    yy, xx = np.ogrid[:binary.shape[0], :binary.shape[1]]
    circular_mask = ((yy - cy_local)**2 + (xx - cx_local)**2) <= (radius * 1.3)**2
    binary = binary & circular_mask

    # Clean up binary mask
    min_obj_size = max(5, int(radius * radius * 0.2))
    binary = morphology.remove_small_objects(binary, min_size=min_obj_size)
    binary = morphology.remove_small_holes(binary, area_threshold=min_obj_size)

    # Label connected components
    labeled = measure.label(binary)

    if labeled.max() == 0:
        return None

    # Find the region closest to the expected center
    local_center = (y - y_min, x - x_min)
    props = measure.regionprops(labeled, intensity_image=region)

    if not props:
        return None

    # Find region whose centroid is closest to our expected center
    best_prop = None
    best_dist = float('inf')
    for prop in props:
        cy, cx = prop.centroid
        dist = np.sqrt((cy - local_center[0])**2 + (cx - local_center[1])**2)
        if dist < best_dist:
            best_dist = dist
            best_prop = prop

    if best_prop is None or best_dist > radius * 1.0:
        return None

    # Check eccentricity
    if best_prop.eccentricity > max_eccentricity:
        return None

    # Check size is reasonable - should be close to LoG estimate
    # Allow 0.5x to 2x the expected size (based on radius)
    expected_diameter = radius * 2
    actual_diameter = best_prop.equivalent_diameter_area
    if actual_diameter < expected_diameter * 0.5 or actual_diameter > expected_diameter * 2.0:
        return None

    # Convert centroid back to image coordinates
    local_cy, local_cx = best_prop.centroid
    global_cy = local_cy + y_min
    global_cx = local_cx + x_min

    return {
        'major_axis': best_prop.axis_major_length,
        'minor_axis': best_prop.axis_minor_length,
        'orientation': best_prop.orientation,
        'eccentricity': best_prop.eccentricity,
        'centroid': (global_cx, global_cy),  # (x, y) format
        'area': best_prop.area,
        'equivalent_diameter': best_prop.equivalent_diameter_area,
    }


def filter_by_size(
    blobs: np.ndarray,
    calibration: CalibrationData,
    min_diameter_um: float = 2.0,
    max_diameter_um: float = 10.0,
) -> np.ndarray:
    """
    Filter blobs by size in micrometers.

    Args:
        blobs: Array of blobs [y, x, sigma]
        calibration: Calibration data for pixel-to-um conversion
        min_diameter_um: Minimum tubercle diameter in µm
        max_diameter_um: Maximum tubercle diameter in µm

    Returns:
        Filtered array of blobs
    """
    if len(blobs) == 0:
        return blobs

    # Blob diameter ≈ 2 * sqrt(2) * sigma
    diameters_px = 2 * np.sqrt(2) * blobs[:, 2]
    diameters_um = diameters_px * calibration.um_per_pixel

    mask = (diameters_um >= min_diameter_um) & (diameters_um <= max_diameter_um)
    return blobs[mask]


def filter_by_edge_distance(
    blobs: np.ndarray,
    image_shape: Tuple[int, int],
    min_edge_distance_px: float = 10,
) -> np.ndarray:
    """
    Filter out blobs too close to image edges.

    Args:
        blobs: Array of blobs [y, x, sigma]
        image_shape: (height, width) of image
        min_edge_distance_px: Minimum distance from edge in pixels

    Returns:
        Filtered array of blobs
    """
    if len(blobs) == 0:
        return blobs

    h, w = image_shape
    y, x = blobs[:, 0], blobs[:, 1]

    mask = (
        (y >= min_edge_distance_px)
        & (y <= h - min_edge_distance_px)
        & (x >= min_edge_distance_px)
        & (x <= w - min_edge_distance_px)
    )
    return blobs[mask]


def blobs_to_tubercles(
    blobs: np.ndarray,
    image: np.ndarray,
    calibration: CalibrationData,
    min_circularity: float = 0.5,
    refine_ellipse: bool = False,
    max_eccentricity: float = 0.9,
) -> List[Tubercle]:
    """
    Convert blob detections to Tubercle objects with measurements.

    Args:
        blobs: Array of blobs [y, x, sigma]
        image: Original image for circularity calculation
        calibration: Calibration data
        min_circularity: Minimum circularity to accept (0-1)
        refine_ellipse: If True, fit ellipses and use equivalent diameter
        max_eccentricity: Maximum eccentricity for ellipse fitting (0=circle, 1=line)

    Returns:
        List of Tubercle objects
    """
    tubercles = []

    for i, blob in enumerate(blobs):
        y, x, sigma = blob

        # Calculate diameter from sigma (initial estimate)
        # For LoG: blob radius ≈ sqrt(2) * sigma
        radius_px = np.sqrt(2) * sigma
        diameter_px = 2 * radius_px

        # Try ellipse refinement if enabled
        ellipse_data = None
        if refine_ellipse:
            ellipse_data = fit_ellipse_to_blob(
                image, (y, x), radius_px, max_eccentricity=max_eccentricity
            )

        if ellipse_data is not None:
            # Use ellipse-based measurements
            diameter_px = ellipse_data['equivalent_diameter']
            area_px = ellipse_data['area']
            # Use refined centroid
            centroid = ellipse_data['centroid']
            # Circularity from eccentricity: circular = low eccentricity
            circularity = 1.0 - ellipse_data['eccentricity']

            # Populate ellipse parameters
            major_axis_px = ellipse_data['major_axis']
            minor_axis_px = ellipse_data['minor_axis']
            major_axis_um = major_axis_px * calibration.um_per_pixel
            minor_axis_um = minor_axis_px * calibration.um_per_pixel
            orientation = ellipse_data['orientation']
            eccentricity = ellipse_data['eccentricity']
        else:
            # Use original LoG-based measurements
            area_px = np.pi * radius_px**2
            centroid = (float(x), float(y))
            circularity = calculate_circularity(image, (y, x), radius_px)
            major_axis_px = None
            minor_axis_px = None
            major_axis_um = None
            minor_axis_um = None
            orientation = None
            eccentricity = None

        # Convert to micrometers
        diameter_um = diameter_px * calibration.um_per_pixel

        # Filter by circularity
        if circularity < min_circularity:
            continue

        tubercle = Tubercle(
            id=len(tubercles) + 1,
            centroid=centroid,
            diameter_px=float(diameter_px),
            diameter_um=float(diameter_um),
            area_px=float(area_px),
            circularity=float(circularity),
            major_axis_px=major_axis_px,
            minor_axis_px=minor_axis_px,
            major_axis_um=major_axis_um,
            minor_axis_um=minor_axis_um,
            orientation=orientation,
            eccentricity=eccentricity,
        )
        tubercles.append(tubercle)

    return tubercles


def detect_tubercles_ellipse(
    image: np.ndarray,
    calibration: CalibrationData,
    min_diameter_um: float = 2.0,
    max_diameter_um: float = 10.0,
    min_circularity: float = 0.5,
    edge_margin_px: int = 10,
    max_eccentricity: float = 0.9,
) -> List[Tubercle]:
    """
    Detect tubercles using threshold segmentation and ellipse fitting.

    This method doesn't use LoG blob detection. Instead, it:
    1. Thresholds the image using adaptive or Otsu's method
    2. Segments connected components
    3. Fits ellipses to each component using regionprops
    4. Filters by size, eccentricity, and edge distance

    Args:
        image: Preprocessed grayscale image (float, 0-1)
        calibration: Calibration data for pixel-to-um conversion
        min_diameter_um: Minimum expected tubercle diameter
        max_diameter_um: Maximum expected tubercle diameter
        min_circularity: Minimum circularity (1 - eccentricity)
        edge_margin_px: Margin from image edges to exclude
        max_eccentricity: Maximum eccentricity allowed

    Returns:
        List of detected Tubercle objects
    """
    h, w = image.shape[:2]

    # Convert diameter limits to pixels
    min_diameter_px = min_diameter_um / calibration.um_per_pixel
    max_diameter_px = max_diameter_um / calibration.um_per_pixel

    # Area limits
    min_area = np.pi * (min_diameter_px / 2) ** 2 * 0.5  # Allow 50% smaller
    max_area = np.pi * (max_diameter_px / 2) ** 2 * 2.0  # Allow 2x larger

    # Threshold using Otsu's method
    try:
        thresh_val = filters.threshold_otsu(image)
    except ValueError:
        thresh_val = 0.5

    binary = image > thresh_val

    # Clean up
    binary = morphology.remove_small_objects(binary, min_size=int(min_area * 0.3))
    binary = morphology.remove_small_holes(binary, area_threshold=int(min_area * 0.5))

    # Optional: watershed to separate touching tubercles
    distance = ndimage.distance_transform_edt(binary)
    local_max_coords = morphology.local_maxima(distance)
    markers = measure.label(local_max_coords)
    labels = segmentation.watershed(-distance, markers, mask=binary)

    # Get region properties
    props = measure.regionprops(labels, intensity_image=image)

    tubercles = []
    for prop in props:
        # Filter by area
        if prop.area < min_area or prop.area > max_area:
            continue

        # Filter by eccentricity
        if prop.eccentricity > max_eccentricity:
            continue

        # Filter by edge distance
        cy, cx = prop.centroid
        if (cy < edge_margin_px or cy > h - edge_margin_px or
            cx < edge_margin_px or cx > w - edge_margin_px):
            continue

        # Calculate equivalent diameter
        equiv_diameter_px = prop.equivalent_diameter_area
        equiv_diameter_um = equiv_diameter_px * calibration.um_per_pixel

        # Filter by diameter
        if equiv_diameter_um < min_diameter_um or equiv_diameter_um > max_diameter_um:
            continue

        # Circularity from eccentricity
        circularity = 1.0 - prop.eccentricity

        if circularity < min_circularity:
            continue

        # Create tubercle
        tubercle = Tubercle(
            id=len(tubercles) + 1,
            centroid=(float(cx), float(cy)),  # (x, y) format
            diameter_px=float(equiv_diameter_px),
            diameter_um=float(equiv_diameter_um),
            area_px=float(prop.area),
            circularity=float(circularity),
            major_axis_px=float(prop.axis_major_length),
            minor_axis_px=float(prop.axis_minor_length),
            major_axis_um=float(prop.axis_major_length * calibration.um_per_pixel),
            minor_axis_um=float(prop.axis_minor_length * calibration.um_per_pixel),
            orientation=float(prop.orientation),
            eccentricity=float(prop.eccentricity),
        )
        tubercles.append(tubercle)

    return tubercles


def detect_tubercles(
    image: np.ndarray,
    calibration: CalibrationData,
    min_diameter_um: float = 2.0,
    max_diameter_um: float = 10.0,
    threshold: float = 0.05,
    min_circularity: float = 0.5,
    edge_margin_px: int = 10,
    method: str = "log",
    min_sigma_override: Optional[float] = None,
    max_sigma_override: Optional[float] = None,
    refine_ellipse: bool = False,
    max_eccentricity: float = 0.9,
    lattice_params: Optional[dict] = None,
) -> List[Tubercle]:
    """
    Detect tubercles in a preprocessed image.

    Main entry point for tubercle detection.

    Args:
        image: Preprocessed grayscale image (float, 0-1)
        calibration: Calibration data for pixel-to-um conversion
        min_diameter_um: Minimum expected tubercle diameter
        max_diameter_um: Maximum expected tubercle diameter
        threshold: Blob detection threshold (lower = more sensitive)
        min_circularity: Minimum circularity filter (0-1)
        edge_margin_px: Margin from image edges to exclude
        method: Detection method ("log", "dog", "ellipse", or "lattice")
        min_sigma_override: Override auto-calculated min sigma
        max_sigma_override: Override auto-calculated max sigma
        refine_ellipse: If True, refine LoG detections with ellipse fitting
        max_eccentricity: Maximum eccentricity for ellipse-based filtering (0=circle, 1=line)
        lattice_params: Optional dict of parameters for lattice method

    Returns:
        List of detected Tubercle objects
    """
    # Calculate sigma range from expected diameters
    # diameter_px = 2 * sqrt(2) * sigma
    # sigma = diameter_px / (2 * sqrt(2))
    min_diameter_px = min_diameter_um / calibration.um_per_pixel
    max_diameter_px = max_diameter_um / calibration.um_per_pixel

    min_sigma = min_diameter_px / (2 * np.sqrt(2))
    max_sigma = max_diameter_px / (2 * np.sqrt(2))

    # Apply overrides if provided
    if min_sigma_override is not None:
        min_sigma = min_sigma_override
    if max_sigma_override is not None:
        max_sigma = max_sigma_override

    # Ensure reasonable sigma values
    min_sigma = max(1.0, min_sigma)
    max_sigma = max(min_sigma + 1, max_sigma)

    # Detect blobs
    if method == "log":
        blobs = detect_blobs_log(
            image,
            min_sigma=min_sigma,
            max_sigma=max_sigma,
            threshold=threshold,
            overlap=0.5,
        )
    elif method == "dog":
        blobs = detect_blobs_dog(
            image,
            min_sigma=min_sigma,
            max_sigma=max_sigma,
            threshold=threshold,
            overlap=0.5,
        )
    elif method == "ellipse":
        # Pure ellipse-based detection (no LoG)
        return detect_tubercles_ellipse(
            image,
            calibration,
            min_diameter_um=min_diameter_um,
            max_diameter_um=max_diameter_um,
            min_circularity=min_circularity,
            edge_margin_px=edge_margin_px,
            max_eccentricity=max_eccentricity,
        )
    elif method == "lattice":
        # Lattice-aware detection using hexagonal pattern
        from .lattice import detect_tubercles_lattice, LatticeParams

        # Build LatticeParams from dict if provided
        params = LatticeParams()
        if lattice_params:
            for key, value in lattice_params.items():
                if hasattr(params, key):
                    setattr(params, key, value)

        tubercles, lattice_model, info = detect_tubercles_lattice(
            image,
            calibration,
            min_diameter_um=min_diameter_um,
            max_diameter_um=max_diameter_um,
            params=params,
            fallback_to_log=True,
        )
        return tubercles
    else:
        raise ValueError(f"Unknown detection method: {method}")

    if len(blobs) == 0:
        return []

    # Filter by size
    blobs = filter_by_size(
        blobs,
        calibration,
        min_diameter_um=min_diameter_um,
        max_diameter_um=max_diameter_um,
    )

    # Filter by edge distance
    blobs = filter_by_edge_distance(blobs, image.shape[:2], edge_margin_px)

    # Convert to Tubercle objects with circularity filtering
    tubercles = blobs_to_tubercles(
        blobs,
        image,
        calibration,
        min_circularity=min_circularity,
        refine_ellipse=refine_ellipse,
        max_eccentricity=max_eccentricity,
    )

    return tubercles
