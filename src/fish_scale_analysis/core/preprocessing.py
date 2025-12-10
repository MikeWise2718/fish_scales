"""Image preprocessing for tubercle detection."""

from pathlib import Path
from typing import Tuple, Union

import numpy as np
from PIL import Image
from skimage import exposure, filters, morphology
from skimage.util import img_as_float, img_as_ubyte


def load_image(path: Union[str, Path]) -> np.ndarray:
    """
    Load an image from disk.

    Supports TIFF, PNG, JPG and other PIL-supported formats.

    Args:
        path: Path to image file

    Returns:
        Image as numpy array (grayscale, float64, range 0-1)
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    # Use PIL for broad format support
    with Image.open(path) as img:
        # Convert to grayscale if needed
        if img.mode != "L":
            img = img.convert("L")
        image = np.array(img)

    # Convert to float in range [0, 1]
    return img_as_float(image)


def to_grayscale(image: np.ndarray) -> np.ndarray:
    """
    Convert image to grayscale if needed.

    Args:
        image: Input image (can be RGB or grayscale)

    Returns:
        Grayscale image as float64
    """
    if image.ndim == 3:
        # RGB to grayscale using luminosity method
        return np.dot(image[..., :3], [0.2989, 0.5870, 0.1140])
    return img_as_float(image)


def apply_clahe(
    image: np.ndarray,
    clip_limit: float = 0.03,
    kernel_size: int = 8,
) -> np.ndarray:
    """
    Apply Contrast Limited Adaptive Histogram Equalization (CLAHE).

    Enhances local contrast, useful for SEM images with uneven illumination.

    Args:
        image: Input grayscale image (float, 0-1)
        clip_limit: Clipping limit for contrast (0-1, default 0.03)
        kernel_size: Size of contextual regions (default 8)

    Returns:
        Enhanced image
    """
    # skimage's equalize_adapthist expects float image in [0, 1]
    return exposure.equalize_adapthist(
        image,
        clip_limit=clip_limit,
        kernel_size=kernel_size,
    )


def apply_gaussian_blur(image: np.ndarray, sigma: float = 1.0) -> np.ndarray:
    """
    Apply Gaussian blur for noise reduction.

    Args:
        image: Input image
        sigma: Standard deviation for Gaussian kernel

    Returns:
        Blurred image
    """
    return filters.gaussian(image, sigma=sigma)


def apply_morphological_opening(
    image: np.ndarray,
    disk_radius: int = 2,
) -> np.ndarray:
    """
    Apply morphological opening to enhance round structures.

    Opening = erosion followed by dilation.
    Helps separate touching tubercles and remove small noise.

    Args:
        image: Input image
        disk_radius: Radius of disk structuring element

    Returns:
        Opened image
    """
    # Convert to uint8 for morphological operations
    img_uint8 = img_as_ubyte(image)

    # Create disk structuring element
    selem = morphology.disk(disk_radius)

    # Apply opening
    opened = morphology.opening(img_uint8, selem)

    return img_as_float(opened)


def apply_tophat(image: np.ndarray, disk_radius: int = 10) -> np.ndarray:
    """
    Apply white top-hat transform to enhance bright spots.

    Top-hat = original - opening
    Enhances bright features smaller than the structuring element.

    Args:
        image: Input image
        disk_radius: Radius of disk structuring element

    Returns:
        Top-hat transformed image
    """
    img_uint8 = img_as_ubyte(image)
    selem = morphology.disk(disk_radius)
    tophat = morphology.white_tophat(img_uint8, selem)
    return img_as_float(tophat)


def normalize_image(image: np.ndarray) -> np.ndarray:
    """
    Normalize image to full [0, 1] range.

    Args:
        image: Input image

    Returns:
        Normalized image with min=0, max=1
    """
    img_min = image.min()
    img_max = image.max()

    if img_max - img_min < 1e-10:
        return np.zeros_like(image)

    return (image - img_min) / (img_max - img_min)


def preprocess_pipeline(
    image: np.ndarray,
    clahe_clip: float = 0.03,
    clahe_kernel: int = 8,
    blur_sigma: float = 1.0,
    use_tophat: bool = False,
    tophat_radius: int = 10,
) -> Tuple[np.ndarray, dict]:
    """
    Complete preprocessing pipeline for tubercle detection.

    Args:
        image: Input grayscale image
        clahe_clip: CLAHE clip limit
        clahe_kernel: CLAHE kernel size
        blur_sigma: Gaussian blur sigma
        use_tophat: Whether to apply top-hat transform
        tophat_radius: Top-hat disk radius

    Returns:
        Tuple of (preprocessed image, dict of intermediate results)
    """
    intermediates = {"original": image.copy()}

    # Step 1: Ensure grayscale float
    gray = to_grayscale(image)
    intermediates["grayscale"] = gray

    # Step 2: Apply CLAHE for contrast enhancement
    enhanced = apply_clahe(gray, clip_limit=clahe_clip, kernel_size=clahe_kernel)
    intermediates["clahe"] = enhanced

    # Step 3: Light Gaussian blur for noise reduction
    blurred = apply_gaussian_blur(enhanced, sigma=blur_sigma)
    intermediates["blurred"] = blurred

    # Step 4: Optional top-hat to enhance bright spots
    if use_tophat:
        result = apply_tophat(blurred, disk_radius=tophat_radius)
        intermediates["tophat"] = result
    else:
        result = blurred

    # Step 5: Final normalization
    result = normalize_image(result)
    intermediates["final"] = result

    return result, intermediates


def get_image_info(image: np.ndarray) -> dict:
    """
    Get basic image statistics.

    Args:
        image: Input image

    Returns:
        Dictionary with image info
    """
    return {
        "shape": image.shape,
        "dtype": str(image.dtype),
        "min": float(image.min()),
        "max": float(image.max()),
        "mean": float(image.mean()),
        "std": float(image.std()),
    }
