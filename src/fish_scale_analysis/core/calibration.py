"""Scale calibration for converting pixels to micrometers."""

from ..models import CalibrationData


def calibrate_manual(scale_bar_um: float, scale_bar_px: float) -> CalibrationData:
    """
    Create calibration from manual scale bar measurements.

    Args:
        scale_bar_um: Length of scale bar in micrometers
        scale_bar_px: Length of scale bar in pixels

    Returns:
        CalibrationData with calculated um/pixel ratio
    """
    if scale_bar_px <= 0:
        raise ValueError("Scale bar pixel length must be positive")
    if scale_bar_um <= 0:
        raise ValueError("Scale bar micrometer length must be positive")

    um_per_pixel = scale_bar_um / scale_bar_px

    return CalibrationData(
        um_per_pixel=um_per_pixel,
        scale_bar_length_um=scale_bar_um,
        scale_bar_length_px=scale_bar_px,
        method="manual",
    )


def estimate_calibration_700x(image_width_px: int = 1024) -> CalibrationData:
    """
    Estimate calibration for typical 700x SEM images.

    Based on analysis of reference papers:
    - Standard magnification: 700x
    - Typical scale bar: 10 µm
    - Typical image width: ~1024 pixels for older SEM images

    For 700x magnification, the field of view is approximately:
    - ~140 µm across for a 1024px wide image
    - This gives ~0.137 µm/pixel

    Args:
        image_width_px: Width of the image in pixels

    Returns:
        CalibrationData with estimated um/pixel ratio
    """
    # Estimated field of view at 700x magnification
    # Based on typical SEM parameters: ~140 µm for 1024px
    estimated_fov_um = 140.0
    reference_width = 1024

    # Scale based on actual image width
    um_per_pixel = (estimated_fov_um / reference_width)

    # For 10 µm scale bar
    scale_bar_um = 10.0
    scale_bar_px = scale_bar_um / um_per_pixel

    return CalibrationData(
        um_per_pixel=um_per_pixel,
        scale_bar_length_um=scale_bar_um,
        scale_bar_length_px=scale_bar_px,
        method="estimated",
    )


def calibrate_from_known_magnification(
    magnification: int,
    image_width_px: int,
    detector_width_mm: float = 10.0,
) -> CalibrationData:
    """
    Calculate calibration from known SEM magnification.

    Args:
        magnification: SEM magnification (e.g., 700)
        image_width_px: Image width in pixels
        detector_width_mm: Physical width of SEM detector (typically 10mm)

    Returns:
        CalibrationData with calculated um/pixel ratio
    """
    # Field of view in mm = detector width / magnification
    fov_mm = detector_width_mm / magnification
    fov_um = fov_mm * 1000  # Convert to micrometers

    um_per_pixel = fov_um / image_width_px

    # Calculate equivalent 10 µm scale bar
    scale_bar_um = 10.0
    scale_bar_px = scale_bar_um / um_per_pixel

    return CalibrationData(
        um_per_pixel=um_per_pixel,
        scale_bar_length_um=scale_bar_um,
        scale_bar_length_px=scale_bar_px,
        method=f"magnification_{magnification}x",
    )
