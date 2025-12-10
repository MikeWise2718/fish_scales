"""
Crop individual SEM figures from composite plate images.
Based on test_cases.md specifications and visual inspection of extracted plates.
"""

from PIL import Image
from pathlib import Path

INPUT_DIR = Path("test_images")
OUTPUT_DIR = Path("test_images")

# Crop coordinates determined by visual inspection of the plates
# Format: (left, top, right, bottom)

# Paper 1 (P1_page2_img1.jpeg) - 6 SEM images in 3x2 grid
# Image is 2505x3481 pixels
# Based on pixel brightness analysis:
# X-axis: Left col ~540-1200, gap ~1200-1450, Right col ~1450-2150
# Y-axis: Row1 starts ~260, gaps at y~900-950 and y~1500-1600
# Row 1: y=260 to y=880
# Row 2: y=970 to y=1480
# Row 3: y=1620 to y=2100
P1_FIGURES = {
    "P1_Fig1_Lepidotes_elvensis_4.78um": (540, 300, 1200, 880),
    "P1_Fig2_Polypterus_bichir_2.63um": (1450, 300, 2150, 880),
    "P1_Fig3_Lepisosteus_osseus_3.79um": (540, 970, 1200, 1480),
    "P1_Fig4_Atractosteus_simplex_7.07um": (1450, 970, 2150, 1480),
    "P1_Fig5_Lepisosteidae_indet_Portugal_3.82um": (540, 1620, 1200, 2100),
    "P1_Fig6_Lepisosteidae_indet_Bolivia_4.50um": (1450, 1620, 2150, 2100),
}

# Paper 2 Plate 1 (P2_page19_img1.jpeg) - Fig 1a and 1b are tubercle surfaces
# Image is 1302x1901 pixels
# Top row has two small SEM images side by side
# Fig 1a: x ~18-320, y ~18-320
# Fig 1b: x ~335-635, y ~18-320
P2_PLATE1_FIGURES = {
    "P2_Pl1_Fig1a_Lepisosteus_platostomus_5.38um": (18, 18, 320, 320),
    "P2_Pl1_Fig1b_Polypterus_ornatipinnis_2.81um": (335, 18, 635, 320),
}

# Paper 3 (P3_page4_img2.jpeg) - Figs 4 and 5 are tubercle surfaces
# Image is 1038x972 pixels
# From grid overlay: top row y=0-185
# Figs are tightly packed; crop aggressively to get clean images
# Fig 4: x=520-670 (skip left edge that bleeds from Fig 3)
# Fig 5: x=700-900
P3_FIGURES = {
    "P3_Fig4_Obaichthys_laevis_5.0um": (520, 8, 665, 175),
    "P3_Fig5_Obaichthys_decoratus_5.0um": (700, 8, 895, 175),
}


def crop_figures(source_image: str, crop_specs: dict):
    """Crop multiple regions from a source image and save them."""
    source_path = INPUT_DIR / source_image

    if not source_path.exists():
        print(f"ERROR: Source image not found: {source_path}")
        return

    img = Image.open(source_path)
    print(f"\nProcessing: {source_image} ({img.width}x{img.height})")

    for output_name, coords in crop_specs.items():
        left, top, right, bottom = coords

        # Validate coordinates
        if right > img.width or bottom > img.height:
            print(f"  WARNING: Crop region {coords} exceeds image bounds, adjusting...")
            right = min(right, img.width)
            bottom = min(bottom, img.height)

        cropped = img.crop((left, top, right, bottom))
        output_path = OUTPUT_DIR / f"{output_name}.tif"

        # Save as TIFF (lossless)
        cropped.save(output_path, format="TIFF")
        print(f"  Saved: {output_name}.tif ({cropped.width}x{cropped.height})")

    img.close()


def main():
    print("Cropping individual SEM figures from composite plates...")
    print("=" * 60)

    # First, let's verify image dimensions
    for img_name in ["P1_page2_img1.jpeg", "P2_page19_img1.jpeg", "P3_page4_img2.jpeg"]:
        img_path = INPUT_DIR / img_name
        if img_path.exists():
            img = Image.open(img_path)
            print(f"{img_name}: {img.width}x{img.height}")
            img.close()

    print("=" * 60)

    # Crop Paper 1 figures
    crop_figures("P1_page2_img1.jpeg", P1_FIGURES)

    # Crop Paper 2 Plate 1 figures
    crop_figures("P2_page19_img1.jpeg", P2_PLATE1_FIGURES)

    # Crop Paper 3 figures
    crop_figures("P3_page4_img2.jpeg", P3_FIGURES)

    print("\n" + "=" * 60)
    print("CROPPING COMPLETE")
    print("=" * 60)

    # List all TIFF files created
    tiff_files = list(OUTPUT_DIR.glob("*.tif"))
    print(f"\nCreated {len(tiff_files)} test case images:")
    for f in sorted(tiff_files):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
