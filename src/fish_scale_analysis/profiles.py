"""Parameter profiles for different image types and species."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DetectionProfile:
    """Parameter profile for tubercle detection."""

    name: str
    description: str

    # Calibration
    calibration_um_per_px: Optional[float] = None  # None = auto-estimate

    # Preprocessing
    clahe_clip: float = 0.03
    clahe_kernel: int = 8
    blur_sigma: float = 1.0
    use_tophat: bool = False
    tophat_radius: int = 10

    # Detection
    threshold: float = 0.05
    min_circularity: float = 0.5
    min_diameter_um: float = 2.0
    max_diameter_um: float = 10.0
    edge_margin_px: int = 10
    min_sigma: Optional[float] = None
    max_sigma: Optional[float] = None


# Built-in profiles
PROFILES = {
    "default": DetectionProfile(
        name="default",
        description="Default parameters for general use",
        clahe_clip=0.03,
        clahe_kernel=8,
        blur_sigma=1.0,
        threshold=0.05,
        min_circularity=0.5,
        min_diameter_um=2.0,
        max_diameter_um=10.0,
    ),
    "paralepidosteus": DetectionProfile(
        name="paralepidosteus",
        description="Optimized for Paralepidosteus sp. (larger tubercles, wide spacing)",
        calibration_um_per_px=0.33,
        clahe_clip=0.03,  # Default preprocessing gives best spacing match
        clahe_kernel=8,
        blur_sigma=1.0,
        use_tophat=False,
        threshold=0.15,  # Tuned: 37 tubercles, 6.29um spacing (ref: 6.00-6.25um)
        min_circularity=0.35,  # Allow some variation in shape
        min_diameter_um=5.0,  # Tuned for reference diameter 5.73-5.94um
        max_diameter_um=15.0,
        edge_margin_px=8,
        # Note: min_sigma/max_sigma left as None to use auto-calculated values
    ),
    "lepisosteus": DetectionProfile(
        name="lepisosteus",
        description="Optimized for Lepisosteus spp. (medium tubercles, close spacing)",
        clahe_clip=0.03,
        clahe_kernel=8,
        blur_sigma=1.0,
        threshold=0.05,
        min_circularity=0.4,
        min_diameter_um=3.0,
        max_diameter_um=8.0,
        edge_margin_px=10,
    ),
    "atractosteus": DetectionProfile(
        name="atractosteus",
        description="Optimized for Atractosteus spp. (large tubercles, tight spacing)",
        clahe_clip=0.03,
        clahe_kernel=8,
        blur_sigma=1.0,
        threshold=0.08,
        min_circularity=0.4,
        min_diameter_um=5.0,
        max_diameter_um=12.0,
        edge_margin_px=10,
    ),
    "polypterus": DetectionProfile(
        name="polypterus",
        description="Optimized for Polypterus spp. (small tubercles, wide spacing)",
        clahe_clip=0.03,
        clahe_kernel=8,
        blur_sigma=0.8,
        threshold=0.03,
        min_circularity=0.5,
        min_diameter_um=1.5,
        max_diameter_um=4.0,
        edge_margin_px=8,
    ),
    "high-contrast": DetectionProfile(
        name="high-contrast",
        description="For high-quality images with clear tubercle boundaries",
        clahe_clip=0.02,
        clahe_kernel=8,
        blur_sigma=0.5,
        threshold=0.08,
        min_circularity=0.6,
        min_diameter_um=2.0,
        max_diameter_um=10.0,
    ),
    "low-contrast": DetectionProfile(
        name="low-contrast",
        description="For noisy/low-quality images with unclear boundaries",
        clahe_clip=0.08,
        clahe_kernel=16,
        blur_sigma=1.5,
        use_tophat=True,
        tophat_radius=12,
        threshold=0.03,
        min_circularity=0.3,
        min_diameter_um=2.0,
        max_diameter_um=10.0,
    ),
    "scanned-pdf": DetectionProfile(
        name="scanned-pdf",
        description="For images extracted from scanned PDFs (like our test images)",
        clahe_clip=0.05,
        clahe_kernel=12,
        blur_sigma=1.0,
        threshold=0.08,
        min_circularity=0.0,  # Disabled due to poor boundary definition
        min_diameter_um=3.0,
        max_diameter_um=10.0,
        edge_margin_px=8,
    ),
}


def get_profile(name: str) -> DetectionProfile:
    """Get a detection profile by name."""
    if name not in PROFILES:
        available = ", ".join(PROFILES.keys())
        raise ValueError(f"Unknown profile '{name}'. Available: {available}")
    return PROFILES[name]


def list_profiles() -> list[str]:
    """List all available profile names."""
    return list(PROFILES.keys())


def profile_help() -> str:
    """Get help text describing all profiles."""
    lines = ["Available profiles:"]
    for name, profile in PROFILES.items():
        lines.append(f"  {name}: {profile.description}")
    return "\n".join(lines)
