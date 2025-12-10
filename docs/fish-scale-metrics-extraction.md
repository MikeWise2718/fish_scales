# Fish Scale Metrics Extraction: High-Level Approach and Pseudo-Code

## Overview

This document describes a high-level approach for extracting two key taxonomic metrics from SEM (Scanning Electron Microscope) images of ganoid fish scales:

1. **Tubercle Diameter** (µm) - The diameter of microscopic tubercles on the ganoine surface
2. **Intertubercular Space** (µm) - The distance between adjacent tubercles

These measurements, as established by Gayet & Meunier (1986, 1993) and Brito et al. (2000), can differentiate between fish families, genera, and sometimes species within Lepisosteidae, Polypteridae, and Semionotidae.

---

## Background: What Are We Measuring?

The external surface of the ganoine (enamel-like layer) on ganoid scales presents microscopic tubercles - small cone-shaped reliefs with blunted tips, typically 2-10 µm in diameter. These are **not visible to the naked eye** and require SEM imaging at approximately 700x magnification.

### Reference Values from Literature

| Family/Genus | Tubercle Diameter (µm) | Intertubercular Space (µm) |
|--------------|------------------------|----------------------------|
| *Lepisosteus* | 3.79 - 5.61 | 3.14 - 4.75 |
| *Atractosteus* | 5.68 - 9.07 | 1.89 - 2.82 |
| *Paralepidosteus* | 5.73 - 5.94 | 6.00 - 6.25 |
| *Polypterus* spp. | 2.19 - 3.03 | 5.57 - 8.54 |
| *Obaichthys* | 4.73 - 5.27 | 4.55 - 4.79 |

---

## High-Level Processing Pipeline

```
┌─────────────────┐
│  INPUT IMAGE    │  (TIFF, SEM micrograph with scale bar)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 1. CALIBRATION  │  Extract µm/pixel ratio from scale bar
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 2. PREPROCESS   │  Enhance contrast, denoise, normalize
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 3. DETECT       │  Identify tubercle centroids and boundaries
│    TUBERCLES    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 4. MEASURE      │  Calculate diameters and spacing
│    METRICS      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 5. OUTPUT       │  Statistics, CSV, visualization
└─────────────────┘
```

---

## Detailed Pseudo-Code

### Step 1: Scale Calibration

```pseudo
FUNCTION extract_scale_calibration(image):
    """
    Extract the µm-per-pixel ratio from the SEM scale bar.
    SEM images typically include a scale bar (e.g., "10 µm" with a line).
    """

    # Option A: Manual input (reliable)
    scale_bar_length_um = USER_INPUT("Enter scale bar length in µm")
    scale_bar_length_px = USER_INPUT("Enter scale bar length in pixels")

    # Option B: Automatic detection (more complex)
    # 1. Look for horizontal lines in bottom region of image
    # 2. Use OCR to read the scale value
    # 3. Measure line length in pixels

    um_per_pixel = scale_bar_length_um / scale_bar_length_px

    RETURN um_per_pixel
```

### Step 2: Image Preprocessing

```pseudo
FUNCTION preprocess_image(image):
    """
    Prepare the SEM image for tubercle detection.
    Tubercles appear as bright spots (elevated areas reflect more electrons).
    """

    # Convert to grayscale if needed
    IF image.channels > 1:
        gray = convert_to_grayscale(image)
    ELSE:
        gray = image

    # Apply Gaussian blur to reduce noise
    # Use small kernel to preserve tubercle edges
    smoothed = gaussian_blur(gray, kernel_size=3)

    # Enhance local contrast (CLAHE - Contrast Limited Adaptive Histogram Equalization)
    # This helps with uneven illumination common in SEM images
    enhanced = apply_CLAHE(smoothed, clip_limit=2.0, tile_size=8)

    # Optional: Apply morphological operations to enhance round structures
    # Opening can help separate touching tubercles
    kernel = create_circular_kernel(radius=2)
    opened = morphological_opening(enhanced, kernel)

    RETURN enhanced, opened
```

### Step 3: Tubercle Detection

```pseudo
FUNCTION detect_tubercles(preprocessed_image, um_per_pixel):
    """
    Detect individual tubercles on the ganoine surface.
    Tubercles are typically 2-10 µm in diameter, appearing as bright circular spots.
    """

    # Calculate expected tubercle size in pixels
    min_diameter_px = 2.0 / um_per_pixel  # 2 µm minimum
    max_diameter_px = 10.0 / um_per_pixel  # 10 µm maximum

    # Method A: Blob Detection (recommended for round structures)
    blobs = detect_blobs(
        image = preprocessed_image,
        method = "LoG",  # Laplacian of Gaussian
        min_sigma = min_diameter_px / 4,
        max_sigma = max_diameter_px / 4,
        threshold = 0.1,  # Adjust based on contrast
        overlap = 0.5
    )

    # Method B: Thresholding + Connected Components (alternative)
    # 1. Apply adaptive thresholding
    binary = adaptive_threshold(preprocessed_image, block_size=11, C=2)

    # 2. Find connected components
    components = find_connected_components(binary)

    # 3. Filter by size and circularity
    tubercles = []
    FOR each component in components:
        area = component.area
        perimeter = component.perimeter
        circularity = 4 * PI * area / (perimeter^2)

        # Tubercles should be roughly circular (circularity > 0.7)
        # and within expected size range
        diameter_px = 2 * sqrt(area / PI)

        IF circularity > 0.7 AND min_diameter_px < diameter_px < max_diameter_px:
            tubercle = {
                centroid: component.centroid,
                diameter_px: diameter_px,
                area: area,
                circularity: circularity
            }
            tubercles.append(tubercle)

    RETURN tubercles
```

### Step 4: Measure Metrics

```pseudo
FUNCTION measure_tubercle_diameter(tubercles, um_per_pixel):
    """
    Calculate the diameter of each detected tubercle.
    Following Gayet & Meunier's methodology, measure the base diameter.
    """

    diameters_um = []

    FOR each tubercle in tubercles:
        # Convert pixel diameter to micrometers
        diameter_um = tubercle.diameter_px * um_per_pixel
        diameters_um.append(diameter_um)

    # Calculate statistics
    mean_diameter = mean(diameters_um)
    std_diameter = standard_deviation(diameters_um)

    RETURN {
        values: diameters_um,
        mean: mean_diameter,
        std: std_diameter,
        n: length(diameters_um)
    }


FUNCTION measure_intertubercular_space(tubercles, um_per_pixel):
    """
    Calculate the spacing between adjacent tubercles.
    Measure edge-to-edge distance (not center-to-center).
    """

    # Build a neighbor graph using Delaunay triangulation
    # This identifies natural neighbors for each tubercle
    centroids = [t.centroid for t in tubercles]
    triangulation = delaunay_triangulation(centroids)

    spaces_um = []

    FOR each edge in triangulation.edges:
        tubercle_a = tubercles[edge.vertex_a]
        tubercle_b = tubercles[edge.vertex_b]

        # Calculate center-to-center distance
        center_distance_px = euclidean_distance(
            tubercle_a.centroid,
            tubercle_b.centroid
        )

        # Calculate edge-to-edge distance (intertubercular space)
        # Subtract the radii of both tubercles
        radius_a_px = tubercle_a.diameter_px / 2
        radius_b_px = tubercle_b.diameter_px / 2

        edge_distance_px = center_distance_px - radius_a_px - radius_b_px

        # Only include positive distances (non-overlapping tubercles)
        IF edge_distance_px > 0:
            edge_distance_um = edge_distance_px * um_per_pixel
            spaces_um.append(edge_distance_um)

    # Calculate statistics
    mean_space = mean(spaces_um)
    std_space = standard_deviation(spaces_um)

    RETURN {
        values: spaces_um,
        mean: mean_space,
        std: std_space,
        n: length(spaces_um)
    }
```

### Step 5: Main Processing Pipeline

```pseudo
FUNCTION process_scale_image(image_path):
    """
    Main function to extract tubercle metrics from a fish scale SEM image.
    """

    # Load image
    image = load_tiff(image_path)

    # Step 1: Get calibration
    um_per_pixel = extract_scale_calibration(image)
    PRINT("Calibration: {um_per_pixel} µm/pixel")

    # Step 2: Preprocess
    enhanced, opened = preprocess_image(image)

    # Step 3: Detect tubercles
    tubercles = detect_tubercles(enhanced, um_per_pixel)
    PRINT("Detected {length(tubercles)} tubercles")

    # Validate detection
    IF length(tubercles) < 10:
        WARN("Few tubercles detected - check image quality or parameters")

    # Step 4: Measure metrics
    diameter_results = measure_tubercle_diameter(tubercles, um_per_pixel)
    space_results = measure_intertubercular_space(tubercles, um_per_pixel)

    # Step 5: Generate output
    results = {
        image: image_path,
        calibration_um_per_px: um_per_pixel,
        n_tubercles: length(tubercles),
        tubercle_diameter: {
            mean: diameter_results.mean,
            std: diameter_results.std,
            unit: "µm"
        },
        intertubercular_space: {
            mean: space_results.mean,
            std: space_results.std,
            unit: "µm"
        }
    }

    RETURN results


FUNCTION batch_process(image_directory, output_csv):
    """
    Process multiple images and compile results for clustering analysis.
    """

    all_results = []

    FOR each image_file in glob(image_directory, "*.tif"):
        TRY:
            result = process_scale_image(image_file)
            all_results.append(result)
        CATCH error:
            LOG_ERROR("Failed to process {image_file}: {error}")

    # Write results to CSV
    write_csv(output_csv, all_results)

    # Generate 2D scatter plot for species clustering
    plot_tubercle_scatter(
        x = [r.tubercle_diameter.mean for r in all_results],
        y = [r.intertubercular_space.mean for r in all_results],
        labels = [r.image for r in all_results],
        xlabel = "Tubercle Diameter (µm)",
        ylabel = "Intertubercular Space (µm)"
    )

    RETURN all_results
```

---

## Key Considerations for Implementation

### Image Quality Requirements
- SEM images at ~700x magnification (as per Gayet & Meunier)
- Clear scale bar visible in image
- Good contrast between tubercles and surrounding ganoine
- Minimal debris or damage on scale surface

### Detection Challenges
1. **Uneven illumination**: Use adaptive thresholding or CLAHE
2. **Touching/overlapping tubercles**: Use watershed segmentation or erosion
3. **Non-circular tubercles**: Adjust circularity threshold; some variation is normal
4. **Surface damage**: Implement outlier detection to exclude anomalous regions

### Validation Approaches
- Compare automated measurements with manual measurements on test images
- Cross-reference results with published values for known species
- Visual overlay of detected tubercles on original image for quality check

### Suggested Python Libraries
- **Image I/O**: `tifffile`, `PIL`
- **Preprocessing**: `scikit-image`, `opencv-python`
- **Blob detection**: `scikit-image.feature.blob_log`
- **Spatial analysis**: `scipy.spatial.Delaunay`
- **Statistics**: `numpy`, `scipy.stats`
- **Visualization**: `matplotlib`

---

## Expected Output Format

```
Sample ID: M_kelleri_HLMD-Me_15576
Tubercles Detected: 127
Tubercle Diameter: 4.52 ± 0.38 µm
Intertubercular Space: 3.89 ± 0.71 µm
Suggested Affinity: Lepisosteus (based on reference ranges)
```

---

## References

- Gayet, M. & Meunier, F.J. (1986). Apport de l'étude de l'ornementation microscopique de la ganoïne dans la détermination de l'appartenance générique et/ou spécifique des écailles isolées. C.R. Acad. Sci. Paris, 303, II (13), pp. 1259-1261.

- Gayet, M. & Meunier, F.J. (1993). Conséquences paléobiogéographiques et biostratigraphiques de l'identification d'écailles ganoïdes du Crétacé supérieur et du Tertiaire inférieur d'Amérique du Sud. Doc. Lab. Géol. Lyon, 125, pp. 169-185.

- Brito, P.M., Meunier, F.J. & Gayet, M. (2000). The morphology and histology of the scales of the Cretaceous gar Obaichthys (Actinopterygii, Lepisosteidae): phylogenetic implications. C.R. Acad. Sci. Paris, 331, pp. 823-829.
