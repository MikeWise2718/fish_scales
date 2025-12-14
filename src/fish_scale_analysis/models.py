"""Data models for fish scale analysis."""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class CalibrationData:
    """Calibration information for converting pixels to micrometers."""

    um_per_pixel: float
    scale_bar_length_um: float
    scale_bar_length_px: float
    method: str  # "manual" or "estimated"

    def px_to_um(self, pixels: float) -> float:
        """Convert pixels to micrometers."""
        return pixels * self.um_per_pixel

    def um_to_px(self, micrometers: float) -> float:
        """Convert micrometers to pixels."""
        return micrometers / self.um_per_pixel


@dataclass
class Tubercle:
    """A single detected tubercle on the scale surface."""

    id: int
    centroid: Tuple[float, float]  # (x, y) in pixels
    diameter_px: float
    diameter_um: float
    area_px: float
    circularity: float
    # Ellipse parameters (optional, populated when using ellipse refinement)
    major_axis_px: Optional[float] = None
    minor_axis_px: Optional[float] = None
    major_axis_um: Optional[float] = None
    minor_axis_um: Optional[float] = None
    orientation: Optional[float] = None  # radians, angle of major axis
    eccentricity: Optional[float] = None  # 0=circle, 1=line

    @property
    def radius_px(self) -> float:
        """Radius in pixels (equivalent circle radius)."""
        return self.diameter_px / 2

    @property
    def radius_um(self) -> float:
        """Radius in micrometers (equivalent circle radius)."""
        return self.diameter_um / 2

    @property
    def aspect_ratio(self) -> Optional[float]:
        """Aspect ratio (major/minor), 1.0 for circle."""
        if self.major_axis_px and self.minor_axis_px and self.minor_axis_px > 0:
            return self.major_axis_px / self.minor_axis_px
        return None


@dataclass
class NeighborEdge:
    """An edge between two neighboring tubercles."""

    tubercle_a_id: int
    tubercle_b_id: int
    center_distance_px: float
    center_distance_um: float
    edge_distance_px: float  # Edge-to-edge (intertubercular space)
    edge_distance_um: float


@dataclass
class MeasurementResult:
    """Complete measurement results for a single image."""

    image_path: str
    calibration: CalibrationData
    n_tubercles: int
    tubercles: List[Tubercle]
    neighbor_edges: List[NeighborEdge]

    # Diameter statistics
    tubercle_diameters_um: List[float] = field(default_factory=list)
    mean_diameter_um: float = 0.0
    std_diameter_um: float = 0.0

    # Spacing statistics
    intertubercular_spaces_um: List[float] = field(default_factory=list)
    mean_space_um: float = 0.0
    std_space_um: float = 0.0

    # Classification
    suggested_genus: Optional[str] = None
    classification_confidence: Optional[str] = None  # "high", "medium", "low"

    def summary_dict(self) -> dict:
        """Return a dictionary summary for CSV output."""
        return {
            "image": self.image_path,
            "n_tubercles": self.n_tubercles,
            "calibration_um_per_px": self.calibration.um_per_pixel,
            "mean_diameter_um": round(self.mean_diameter_um, 2),
            "std_diameter_um": round(self.std_diameter_um, 2),
            "mean_space_um": round(self.mean_space_um, 2),
            "std_space_um": round(self.std_space_um, 2),
            "suggested_genus": self.suggested_genus or "Unknown",
            "confidence": self.classification_confidence or "N/A",
        }


# Reference ranges for genus classification (from Gayet & Meunier papers)
GENUS_REFERENCE_RANGES = {
    "Lepisosteus": {
        "diameter_min": 3.79,
        "diameter_max": 5.61,
        "space_min": 3.14,
        "space_max": 4.75,
    },
    "Atractosteus": {
        "diameter_min": 5.68,
        "diameter_max": 9.07,
        "space_min": 1.89,
        "space_max": 2.82,
    },
    "Polypterus": {
        "diameter_min": 2.19,
        "diameter_max": 3.03,
        "space_min": 5.57,
        "space_max": 8.54,
    },
    "Obaichthys": {
        "diameter_min": 4.73,
        "diameter_max": 5.27,
        "space_min": 4.55,
        "space_max": 4.79,
    },
    "Paralepidosteus": {
        "diameter_min": 5.73,
        "diameter_max": 5.94,
        "space_min": 6.00,
        "space_max": 6.25,
    },
    "Lepidotes": {
        "diameter_min": 3.93,
        "diameter_max": 4.78,
        "space_min": 4.57,
        "space_max": 5.02,
    },
}
