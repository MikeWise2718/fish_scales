"""Tubercle detection using blob detection algorithms."""

from typing import List, Optional, Tuple

import numpy as np
from scipy import ndimage
from skimage import measure
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
) -> List[Tubercle]:
    """
    Convert blob detections to Tubercle objects with measurements.

    Args:
        blobs: Array of blobs [y, x, sigma]
        image: Original image for circularity calculation
        calibration: Calibration data
        min_circularity: Minimum circularity to accept (0-1)

    Returns:
        List of Tubercle objects
    """
    tubercles = []

    for i, blob in enumerate(blobs):
        y, x, sigma = blob

        # Calculate diameter from sigma
        # For LoG: blob radius ≈ sqrt(2) * sigma
        radius_px = np.sqrt(2) * sigma
        diameter_px = 2 * radius_px

        # Convert to micrometers
        diameter_um = diameter_px * calibration.um_per_pixel

        # Calculate area
        area_px = np.pi * radius_px**2

        # Calculate circularity
        circularity = calculate_circularity(image, (y, x), radius_px)

        # Filter by circularity
        if circularity < min_circularity:
            continue

        tubercle = Tubercle(
            id=len(tubercles) + 1,
            centroid=(float(x), float(y)),  # (x, y) format
            diameter_px=float(diameter_px),
            diameter_um=float(diameter_um),
            area_px=float(area_px),
            circularity=float(circularity),
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
        method: Detection method ("log" or "dog")

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
    )

    return tubercles
