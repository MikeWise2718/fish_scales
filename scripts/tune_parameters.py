#!/usr/bin/env python
"""
Parameter tuning script for tubercle detection.

Performs grid search over preprocessing and detection parameters
to find optimal settings for a given test image.
"""

import itertools
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fish_scale_analysis.core.calibration import estimate_calibration_700x, calibrate_manual
from fish_scale_analysis.core.preprocessing import load_image, preprocess_pipeline
from fish_scale_analysis.core.detection import detect_tubercles
from fish_scale_analysis.core.measurement import measure_metrics

console = Console()


@dataclass
class TuningResult:
    """Result from a single parameter combination."""
    params: dict
    n_tubercles: int
    mean_diameter_um: float
    std_diameter_um: float
    mean_space_um: float
    std_space_um: float
    score: float
    error: Optional[str] = None


def score_detection(
    n_tubercles: int,
    mean_diameter: float,
    mean_spacing: float,
    expected_count: int,
    expected_diameter: float,
    expected_spacing: float,
    count_tolerance: float = 0.3,  # 30% tolerance on count
    diameter_tolerance: float = 0.5,  # µm
    spacing_tolerance: float = 0.7,  # µm
) -> float:
    """
    Score detection quality against expected values.

    Returns a score from 0 to 1, where 1 is perfect match.
    """
    # Count score: penalize deviation from expected
    if expected_count > 0:
        count_ratio = n_tubercles / expected_count
        # Score 1.0 if within tolerance, decreasing outside
        if 1 - count_tolerance <= count_ratio <= 1 + count_tolerance:
            count_score = 1.0 - abs(1 - count_ratio) / count_tolerance * 0.5
        else:
            count_score = max(0, 0.5 - abs(1 - count_ratio - count_tolerance))
    else:
        count_score = 0.5  # No expected count

    # Diameter score
    diam_error = abs(mean_diameter - expected_diameter)
    diam_score = max(0, 1.0 - diam_error / (diameter_tolerance * 2))

    # Spacing score
    space_error = abs(mean_spacing - expected_spacing)
    space_score = max(0, 1.0 - space_error / (spacing_tolerance * 2))

    # Weighted combination (count matters less since it varies with image region)
    return 0.25 * count_score + 0.375 * diam_score + 0.375 * space_score


def run_detection_with_params(
    image: np.ndarray,
    calibration,
    preprocess_params: dict,
    detection_params: dict,
) -> TuningResult:
    """Run detection with specific parameters and return results."""

    params = {**preprocess_params, **detection_params}

    try:
        # Preprocess
        preprocessed, _ = preprocess_pipeline(
            image,
            clahe_clip=preprocess_params.get("clahe_clip", 0.03),
            clahe_kernel=preprocess_params.get("clahe_kernel", 8),
            blur_sigma=preprocess_params.get("blur_sigma", 1.0),
            use_tophat=preprocess_params.get("use_tophat", False),
            tophat_radius=preprocess_params.get("tophat_radius", 10),
        )

        # Detect
        tubercles = detect_tubercles(
            preprocessed,
            calibration,
            min_diameter_um=detection_params.get("min_diameter_um", 2.0),
            max_diameter_um=detection_params.get("max_diameter_um", 10.0),
            threshold=detection_params.get("threshold", 0.05),
            min_circularity=detection_params.get("min_circularity", 0.5),
            edge_margin_px=detection_params.get("edge_margin_px", 10),
        )

        if len(tubercles) < 3:
            return TuningResult(
                params=params,
                n_tubercles=len(tubercles),
                mean_diameter_um=0,
                std_diameter_um=0,
                mean_space_um=0,
                std_space_um=0,
                score=0,
                error="Too few tubercles"
            )

        # Measure
        result = measure_metrics(tubercles, calibration, "tuning")

        return TuningResult(
            params=params,
            n_tubercles=result.n_tubercles,
            mean_diameter_um=result.mean_diameter_um,
            std_diameter_um=result.std_diameter_um,
            mean_space_um=result.mean_space_um,
            std_space_um=result.std_space_um,
            score=0,  # Will be calculated after
        )

    except Exception as e:
        return TuningResult(
            params=params,
            n_tubercles=0,
            mean_diameter_um=0,
            std_diameter_um=0,
            mean_space_um=0,
            std_space_um=0,
            score=0,
            error=str(e)
        )


def grid_search(
    image_path: Path,
    expected_count: int,
    expected_diameter: float,
    expected_spacing: float,
    calibration_um_per_px: Optional[float] = None,
) -> list[TuningResult]:
    """
    Perform grid search over parameter space.
    """

    # Load image
    image = load_image(image_path)

    # Calibration
    if calibration_um_per_px:
        # Create manual calibration
        from fish_scale_analysis.models import CalibrationData
        calibration = CalibrationData(
            um_per_pixel=calibration_um_per_px,
            scale_bar_length_um=10.0,
            scale_bar_length_px=10.0 / calibration_um_per_px,
            method="manual",
        )
    else:
        calibration = estimate_calibration_700x(image.shape[1])

    console.print(f"[cyan]Image size:[/cyan] {image.shape[1]}x{image.shape[0]} pixels")
    console.print(f"[cyan]Calibration:[/cyan] {calibration.um_per_pixel:.4f} µm/pixel")

    # Define parameter grid
    preprocess_grid = {
        "clahe_clip": [0.02, 0.03, 0.05, 0.08],
        "clahe_kernel": [8, 12, 16],
        "blur_sigma": [0.5, 1.0, 1.5],
        "use_tophat": [False, True],
        "tophat_radius": [8, 12],  # Only used if use_tophat=True
    }

    detection_grid = {
        "threshold": [0.01, 0.02, 0.03, 0.05, 0.08],
        "min_circularity": [0.3, 0.4, 0.5, 0.6],
        "min_diameter_um": [3.0, 4.0, 5.0],
        "max_diameter_um": [8.0, 10.0, 12.0],
        "edge_margin_px": [5, 10],
    }

    # Generate all combinations (reduce for efficiency)
    # For tophat, only vary tophat_radius when use_tophat=True
    preprocess_combos = []
    for clip in preprocess_grid["clahe_clip"]:
        for kernel in preprocess_grid["clahe_kernel"]:
            for blur in preprocess_grid["blur_sigma"]:
                # Without tophat
                preprocess_combos.append({
                    "clahe_clip": clip,
                    "clahe_kernel": kernel,
                    "blur_sigma": blur,
                    "use_tophat": False,
                    "tophat_radius": 10,
                })
                # With tophat
                for radius in preprocess_grid["tophat_radius"]:
                    preprocess_combos.append({
                        "clahe_clip": clip,
                        "clahe_kernel": kernel,
                        "blur_sigma": blur,
                        "use_tophat": True,
                        "tophat_radius": radius,
                    })

    detection_combos = []
    for thresh in detection_grid["threshold"]:
        for circ in detection_grid["min_circularity"]:
            for min_d in detection_grid["min_diameter_um"]:
                for max_d in detection_grid["max_diameter_um"]:
                    for edge in detection_grid["edge_margin_px"]:
                        detection_combos.append({
                            "threshold": thresh,
                            "min_circularity": circ,
                            "min_diameter_um": min_d,
                            "max_diameter_um": max_d,
                            "edge_margin_px": edge,
                        })

    total_combos = len(preprocess_combos) * len(detection_combos)
    console.print(f"[yellow]Testing {total_combos} parameter combinations...[/yellow]")

    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Tuning...", total=total_combos)

        for pp in preprocess_combos:
            for dp in detection_combos:
                result = run_detection_with_params(image, calibration, pp, dp)

                # Calculate score
                if result.error is None:
                    result.score = score_detection(
                        result.n_tubercles,
                        result.mean_diameter_um,
                        result.mean_space_um,
                        expected_count,
                        expected_diameter,
                        expected_spacing,
                    )

                results.append(result)
                progress.advance(task)

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)

    return results


def quick_search(
    image_path: Path,
    expected_count: int,
    expected_diameter: float,
    expected_spacing: float,
    calibration_um_per_px: Optional[float] = None,
) -> list[TuningResult]:
    """
    Quick search with reduced parameter space.
    """

    # Load image
    image = load_image(image_path)

    # Calibration
    if calibration_um_per_px:
        from fish_scale_analysis.models import CalibrationData
        calibration = CalibrationData(
            um_per_pixel=calibration_um_per_px,
            scale_bar_length_um=10.0,
            scale_bar_length_px=10.0 / calibration_um_per_px,
            method="manual",
        )
    else:
        calibration = estimate_calibration_700x(image.shape[1])

    console.print(f"[cyan]Image size:[/cyan] {image.shape[1]}x{image.shape[0]} pixels")
    console.print(f"[cyan]Calibration:[/cyan] {calibration.um_per_pixel:.4f} µm/pixel")

    # Reduced grid for quick search
    preprocess_combos = [
        {"clahe_clip": 0.03, "clahe_kernel": 8, "blur_sigma": 1.0, "use_tophat": False, "tophat_radius": 10},
        {"clahe_clip": 0.05, "clahe_kernel": 8, "blur_sigma": 1.0, "use_tophat": False, "tophat_radius": 10},
        {"clahe_clip": 0.05, "clahe_kernel": 12, "blur_sigma": 0.5, "use_tophat": False, "tophat_radius": 10},
        {"clahe_clip": 0.03, "clahe_kernel": 8, "blur_sigma": 1.0, "use_tophat": True, "tophat_radius": 10},
        {"clahe_clip": 0.05, "clahe_kernel": 8, "blur_sigma": 0.5, "use_tophat": True, "tophat_radius": 12},
        {"clahe_clip": 0.08, "clahe_kernel": 16, "blur_sigma": 1.0, "use_tophat": True, "tophat_radius": 10},
    ]

    detection_combos = [
        {"threshold": 0.01, "min_circularity": 0.3, "min_diameter_um": 4.0, "max_diameter_um": 10.0, "edge_margin_px": 5},
        {"threshold": 0.02, "min_circularity": 0.3, "min_diameter_um": 4.0, "max_diameter_um": 10.0, "edge_margin_px": 5},
        {"threshold": 0.02, "min_circularity": 0.4, "min_diameter_um": 4.0, "max_diameter_um": 10.0, "edge_margin_px": 5},
        {"threshold": 0.03, "min_circularity": 0.4, "min_diameter_um": 4.0, "max_diameter_um": 10.0, "edge_margin_px": 5},
        {"threshold": 0.03, "min_circularity": 0.5, "min_diameter_um": 3.0, "max_diameter_um": 10.0, "edge_margin_px": 10},
        {"threshold": 0.05, "min_circularity": 0.4, "min_diameter_um": 4.0, "max_diameter_um": 10.0, "edge_margin_px": 5},
        {"threshold": 0.05, "min_circularity": 0.5, "min_diameter_um": 3.0, "max_diameter_um": 10.0, "edge_margin_px": 10},
        {"threshold": 0.08, "min_circularity": 0.4, "min_diameter_um": 4.0, "max_diameter_um": 12.0, "edge_margin_px": 5},
    ]

    total_combos = len(preprocess_combos) * len(detection_combos)
    console.print(f"[yellow]Quick search: {total_combos} parameter combinations...[/yellow]")

    results = []

    for pp in preprocess_combos:
        for dp in detection_combos:
            result = run_detection_with_params(image, calibration, pp, dp)

            if result.error is None:
                result.score = score_detection(
                    result.n_tubercles,
                    result.mean_diameter_um,
                    result.mean_space_um,
                    expected_count,
                    expected_diameter,
                    expected_spacing,
                )

            results.append(result)

    results.sort(key=lambda r: r.score, reverse=True)
    return results


def print_results(results: list[TuningResult], top_n: int = 20):
    """Print top results in a table."""

    table = Table(title=f"Top {top_n} Parameter Combinations")
    table.add_column("Rank", style="cyan", width=4)
    table.add_column("Score", style="green", width=6)
    table.add_column("n", width=4)
    table.add_column("Diam (µm)", width=10)
    table.add_column("Space (µm)", width=10)
    table.add_column("thresh", width=6)
    table.add_column("circ", width=5)
    table.add_column("CLAHE", width=6)
    table.add_column("blur", width=5)
    table.add_column("tophat", width=6)

    for i, r in enumerate(results[:top_n]):
        if r.error:
            continue

        table.add_row(
            str(i + 1),
            f"{r.score:.3f}",
            str(r.n_tubercles),
            f"{r.mean_diameter_um:.2f}±{r.std_diameter_um:.2f}",
            f"{r.mean_space_um:.2f}±{r.std_space_um:.2f}",
            f"{r.params.get('threshold', 0):.2f}",
            f"{r.params.get('min_circularity', 0):.1f}",
            f"{r.params.get('clahe_clip', 0):.2f}",
            f"{r.params.get('blur_sigma', 0):.1f}",
            "yes" if r.params.get('use_tophat') else "no",
        )

    console.print(table)


def save_best_params(results: list[TuningResult], output_path: Path):
    """Save best parameters to JSON file."""
    if not results or results[0].error:
        return

    best = results[0]

    config = {
        "preprocessing": {
            "clahe_clip": best.params.get("clahe_clip"),
            "clahe_kernel": best.params.get("clahe_kernel"),
            "blur_sigma": best.params.get("blur_sigma"),
            "use_tophat": best.params.get("use_tophat"),
            "tophat_radius": best.params.get("tophat_radius"),
        },
        "detection": {
            "threshold": best.params.get("threshold"),
            "min_circularity": best.params.get("min_circularity"),
            "min_diameter_um": best.params.get("min_diameter_um"),
            "max_diameter_um": best.params.get("max_diameter_um"),
            "edge_margin_px": best.params.get("edge_margin_px"),
        },
        "results": {
            "score": best.score,
            "n_tubercles": best.n_tubercles,
            "mean_diameter_um": best.mean_diameter_um,
            "std_diameter_um": best.std_diameter_um,
            "mean_space_um": best.mean_space_um,
            "std_space_um": best.std_space_um,
        }
    }

    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    console.print(f"\n[green]Best parameters saved to:[/green] {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Tune tubercle detection parameters")
    parser.add_argument("image", type=Path, help="Path to test image")
    parser.add_argument("--expected-count", type=int, default=43, help="Expected tubercle count")
    parser.add_argument("--expected-diameter", type=float, default=5.83, help="Expected mean diameter (µm)")
    parser.add_argument("--expected-spacing", type=float, default=6.12, help="Expected mean spacing (µm)")
    parser.add_argument("--calibration", type=float, default=None, help="Manual calibration (µm/pixel)")
    parser.add_argument("--quick", action="store_true", help="Quick search with reduced parameter space")
    parser.add_argument("--full", action="store_true", help="Full grid search (slow)")
    parser.add_argument("--output", type=Path, default=None, help="Save best params to JSON file")
    parser.add_argument("--top", type=int, default=20, help="Show top N results")

    args = parser.parse_args()

    if not args.image.exists():
        console.print(f"[red]Image not found:[/red] {args.image}")
        return 1

    console.print(f"\n[bold]Tuning parameters for:[/bold] {args.image.name}")
    console.print(f"[bold]Expected:[/bold] count={args.expected_count}, diameter={args.expected_diameter}µm, spacing={args.expected_spacing}µm\n")

    if args.full:
        results = grid_search(
            args.image,
            args.expected_count,
            args.expected_diameter,
            args.expected_spacing,
            args.calibration,
        )
    else:
        results = quick_search(
            args.image,
            args.expected_count,
            args.expected_diameter,
            args.expected_spacing,
            args.calibration,
        )

    print_results(results, args.top)

    # Print best result details
    if results and results[0].error is None:
        best = results[0]
        console.print("\n[bold green]Best Parameters:[/bold green]")
        console.print(f"  threshold: {best.params.get('threshold')}")
        console.print(f"  min_circularity: {best.params.get('min_circularity')}")
        console.print(f"  min_diameter_um: {best.params.get('min_diameter_um')}")
        console.print(f"  max_diameter_um: {best.params.get('max_diameter_um')}")
        console.print(f"  clahe_clip: {best.params.get('clahe_clip')}")
        console.print(f"  clahe_kernel: {best.params.get('clahe_kernel')}")
        console.print(f"  blur_sigma: {best.params.get('blur_sigma')}")
        console.print(f"  use_tophat: {best.params.get('use_tophat')}")
        if best.params.get('use_tophat'):
            console.print(f"  tophat_radius: {best.params.get('tophat_radius')}")

    if args.output:
        save_best_params(results, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
