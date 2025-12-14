"""Command-line interface for fish scale analysis."""

import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich_argparse import RichHelpFormatter

import argparse

from .core.calibration import calibrate_manual, estimate_calibration_700x
from .core.preprocessing import load_image, preprocess_pipeline
from .core.detection import detect_tubercles
from .core.measurement import measure_metrics, process_image
from .output.csv_writer import write_all_outputs, append_to_batch_csv
from .output.logger import (
    setup_logger,
    log_image_start,
    log_calibration,
    log_preprocessing,
    log_detection,
    log_measurement,
    log_classification,
    log_output,
    log_warning,
    log_error,
    create_session_dir,
)
from .output.visualization import (
    create_combined_figure,
    create_scatter_plot,
    create_preprocessing_figure,
)

console = Console()


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="fish-scale-measure",
        description="Extract tubercle metrics from fish scale SEM images",
        epilog="Run 'fish-scale-measure <command> --help' for command-specific options.\n"
               "Reference image: test_images/P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif",
        formatter_class=RichHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Process command
    process_parser = subparsers.add_parser(
        "process",
        help="Process a single image",
        formatter_class=RichHelpFormatter,
    )
    process_parser.add_argument(
        "image",
        type=str,
        help="Path to TIFF image file, or short alias (e.g., 'ref', 'P1.1', 'P1.2', etc.)",
    )
    process_parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("output"),
        help="Output directory (default: ./output)",
    )
    process_parser.add_argument(
        "--scale-bar-um",
        type=float,
        default=None,
        help="Scale bar length in µm (default: auto-estimate for 700x)",
    )
    process_parser.add_argument(
        "--scale-bar-px",
        type=float,
        default=None,
        help="Scale bar length in pixels (required with --scale-bar-um)",
    )
    process_parser.add_argument(
        "--min-diameter",
        type=float,
        default=None,
        help="Minimum expected tubercle diameter in µm (default: 2.0, or from profile)",
    )
    process_parser.add_argument(
        "--max-diameter",
        type=float,
        default=None,
        help="Maximum expected tubercle diameter in µm (default: 10.0, or from profile)",
    )
    process_parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Blob detection threshold, lower=more sensitive (default: 0.05, or from profile)",
    )
    process_parser.add_argument(
        "--circularity",
        type=float,
        default=None,
        help="Minimum circularity filter 0-1 (default: 0.5, or from profile)",
    )
    # Preprocessing parameters
    process_parser.add_argument(
        "--clahe-clip",
        type=float,
        default=None,
        help="CLAHE clip limit for contrast enhancement (default: 0.03, or from profile)",
    )
    process_parser.add_argument(
        "--clahe-kernel",
        type=int,
        default=None,
        help="CLAHE kernel size (default: 8, or from profile)",
    )
    process_parser.add_argument(
        "--blur-sigma",
        type=float,
        default=None,
        help="Gaussian blur sigma for noise reduction (default: 1.0)",
    )
    process_parser.add_argument(
        "--use-tophat",
        action="store_true",
        help="Apply top-hat transform to enhance bright spots",
    )
    process_parser.add_argument(
        "--tophat-radius",
        type=int,
        default=10,
        help="Top-hat disk radius in pixels (default: 10)",
    )
    # Detection parameters
    process_parser.add_argument(
        "--method",
        type=str,
        choices=["log", "dog", "ellipse", "lattice"],
        default="log",
        help="Detection method: log (Laplacian of Gaussian), dog (Difference of Gaussian), ellipse (threshold + ellipse fitting), lattice (hexagonal lattice-aware detection)",
    )
    process_parser.add_argument(
        "--refine-ellipse",
        action="store_true",
        help="Refine LoG/DoG detections by fitting ellipses (improves diameter accuracy for non-circular tubercles)",
    )
    process_parser.add_argument(
        "--max-eccentricity",
        type=float,
        default=0.9,
        help="Maximum eccentricity for ellipse filtering (0=circle, 1=line, default: 0.9)",
    )
    process_parser.add_argument(
        "--min-sigma",
        type=float,
        default=None,
        help="Minimum sigma for blob detection (default: auto from diameter)",
    )
    process_parser.add_argument(
        "--max-sigma",
        type=float,
        default=None,
        help="Maximum sigma for blob detection (default: auto from diameter)",
    )
    process_parser.add_argument(
        "--edge-margin",
        type=int,
        default=10,
        help="Edge margin in pixels to exclude detections (default: 10)",
    )
    process_parser.add_argument(
        "--neighbor-graph",
        type=str,
        choices=["delaunay", "gabriel", "rng"],
        default="delaunay",
        help="Neighbor graph for spacing: delaunay (all edges), gabriel (fewer), rng (most conservative, recommended)",
    )
    # Lattice method parameters
    process_parser.add_argument(
        "--seed-threshold",
        type=float,
        default=None,
        help="Seed detection threshold for lattice method (default: 0.08, stricter than normal)",
    )
    process_parser.add_argument(
        "--min-seeds",
        type=int,
        default=None,
        help="Minimum number of seeds required for lattice method (default: 5)",
    )
    process_parser.add_argument(
        "--lattice-regularity",
        type=float,
        default=None,
        help="Minimum lattice regularity score 0-1 (default: 0.5)",
    )
    process_parser.add_argument(
        "--max-edge-factor",
        type=float,
        default=None,
        help="Filter edges longer than this factor × median distance (e.g., 1.5 removes outliers)",
    )
    process_parser.add_argument(
        "--calibration",
        type=float,
        default=None,
        help="Manual calibration in µm/pixel (overrides scale bar)",
    )
    process_parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Use preset parameter profile (e.g., paralepidosteus, polypterus, scanned-pdf)",
    )
    process_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    process_parser.add_argument(
        "--no-viz",
        action="store_true",
        help="Skip visualization generation",
    )
    process_parser.add_argument(
        "--show-preprocessing",
        action="store_true",
        help="Generate preprocessing steps visualization",
    )
    process_parser.add_argument(
        "--label-mode",
        type=str,
        choices=["id", "diameter", "spacing"],
        default="id",
        help="Diagram labels: id (number only), diameter (number + size), spacing (number + size + distances)",
    )
    process_parser.add_argument(
        "--spacing-method",
        type=str,
        choices=["nearest", "graph"],
        default="nearest",
        help="Spacing calculation: nearest (nearest-neighbor, matches paper methodology), graph (all graph edges)",
    )

    # Batch command
    batch_parser = subparsers.add_parser(
        "batch",
        help="Process multiple images",
        formatter_class=RichHelpFormatter,
    )
    batch_parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing TIFF images",
    )
    batch_parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("output"),
        help="Output directory (default: ./output)",
    )
    batch_parser.add_argument(
        "--scale-bar-um",
        type=float,
        default=None,
        help="Scale bar length in µm",
    )
    batch_parser.add_argument(
        "--scale-bar-px",
        type=float,
        default=None,
        help="Scale bar length in pixels",
    )
    batch_parser.add_argument(
        "--min-diameter",
        type=float,
        default=2.0,
        help="Minimum expected tubercle diameter in µm",
    )
    batch_parser.add_argument(
        "--max-diameter",
        type=float,
        default=10.0,
        help="Maximum expected tubercle diameter in µm",
    )
    batch_parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Blob detection threshold",
    )
    batch_parser.add_argument(
        "--circularity",
        type=float,
        default=0.5,
        help="Minimum circularity filter",
    )
    batch_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    batch_parser.add_argument(
        "--no-viz",
        action="store_true",
        help="Skip visualization generation",
    )
    batch_parser.add_argument(
        "--scatter",
        action="store_true",
        help="Generate scatter plot of all results",
    )

    # Benchmark command (compare measured vs expected values from literature)
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Compare measurements against expected values from literature",
        formatter_class=RichHelpFormatter,
    )
    benchmark_parser.add_argument(
        "--test-dir",
        type=Path,
        default=Path("test_images"),
        help="Directory containing test images (default: ./test_images)",
    )
    benchmark_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    return parser


# Test image aliases for quick access
TEST_IMAGE_ALIASES = {
    # Reference image
    "ref": "test_images/P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif",
    # Paper 1 images
    "P1.1": "test_images/P1_Fig1_Lepidotes_elvensis_4.78um.tif",
    "P1.2": "test_images/P1_Fig2_Polypterus_bichir_2.63um.tif",
    "P1.3": "test_images/P1_Fig3_Lepisosteus_osseus_3.79um.tif",
    "P1.4": "test_images/P1_Fig4_Atractosteus_simplex_7.07um.tif",
    "P1.5": "test_images/P1_Fig5_Lepisosteidae_indet_Portugal_3.82um.tif",
    "P1.6": "test_images/P1_Fig6_Lepisosteidae_indet_Bolivia_4.50um.tif",
    # Paper 2 images
    "P2.1c": "test_images/P2_Fig1c_Paralepidosteus_sp_Acre_5.73um.tif",
    "P2.1d": "test_images/P2_Fig1d_Lepisosteus_platyrhinchus_3.95um.tif",
    "P2.1e": "test_images/P2_Fig1e_Polypterus_delhezi_2.19um.tif",
    "P2.1a": "test_images/P2_Pl1_Fig1a_Lepisosteus_platostomus_5.38um.tif",
    "P2.1b": "test_images/P2_Pl1_Fig1b_Polypterus_ornatipinnis_2.81um.tif",
    # Paper 3 images
    "P3.4": "test_images/P3_Fig4_Obaichthys_laevis_5.0um.tif",
    "P3.5": "test_images/P3_Fig5_Obaichthys_decoratus_5.0um.tif",
}


def resolve_image_path(image_arg: str) -> Path:
    """Resolve image argument to a path, handling aliases (case-insensitive)."""
    # Try exact match first
    if image_arg in TEST_IMAGE_ALIASES:
        return Path(TEST_IMAGE_ALIASES[image_arg])
    # Try case-insensitive match
    image_lower = image_arg.lower()
    for alias, path in TEST_IMAGE_ALIASES.items():
        if alias.lower() == image_lower:
            return Path(path)
    return Path(image_arg)


def process_single_image(args: argparse.Namespace) -> int:
    """Process a single image."""
    # Create session directory
    session_dir = create_session_dir(args.output)
    logger = setup_logger(session_dir)

    image_path = resolve_image_path(args.image)
    if not image_path.exists():
        log_error(logger, f"Image not found: {image_path}")
        return 1

    log_image_start(logger, str(image_path))

    # Load profile if specified
    profile = None
    if args.profile:
        from .profiles import get_profile
        try:
            profile = get_profile(args.profile)
            if args.verbose:
                console.print(f"[cyan]Using profile:[/cyan] {profile.name} - {profile.description}")
        except ValueError as e:
            log_error(logger, str(e))
            return 1

    try:
        # Load image
        image = load_image(image_path)

        # Calibration (profile < CLI args < explicit calibration)
        calibration_um = args.calibration
        if calibration_um is None and profile and profile.calibration_um_per_px:
            calibration_um = profile.calibration_um_per_px

        if calibration_um:
            # Direct µm/pixel calibration
            from .models import CalibrationData
            calibration = CalibrationData(
                um_per_pixel=calibration_um,
                scale_bar_length_um=10.0,
                scale_bar_length_px=10.0 / calibration_um,
                method="manual" if args.calibration else "profile",
            )
        elif args.scale_bar_um and args.scale_bar_px:
            calibration = calibrate_manual(args.scale_bar_um, args.scale_bar_px)
        else:
            calibration = estimate_calibration_700x(image.shape[1])
            log_warning(logger, "Using estimated calibration for 700x magnification")

        log_calibration(
            logger,
            calibration.um_per_pixel,
            calibration.method,
            calibration.scale_bar_length_um,
            calibration.scale_bar_length_px,
        )

        # Get parameters (CLI overrides profile defaults)
        def get_param(name, cli_val, default):
            if cli_val is not None:  # CLI explicitly set
                return cli_val
            if profile and hasattr(profile, name):
                return getattr(profile, name)
            return default

        # Preprocess with configurable parameters
        clahe_clip = get_param("clahe_clip", args.clahe_clip, 0.03)
        clahe_kernel = get_param("clahe_kernel", args.clahe_kernel, 8)
        blur_sigma = get_param("blur_sigma", args.blur_sigma, 1.0)
        use_tophat = args.use_tophat or (profile and profile.use_tophat)
        tophat_radius = get_param("tophat_radius", args.tophat_radius, 10)

        preprocessed, intermediates = preprocess_pipeline(
            image,
            clahe_clip=clahe_clip,
            clahe_kernel=clahe_kernel,
            blur_sigma=blur_sigma,
            use_tophat=use_tophat,
            tophat_radius=tophat_radius,
        )
        preprocess_desc = f"CLAHE(clip={clahe_clip}, kernel={clahe_kernel}) + blur(σ={blur_sigma})"
        if use_tophat:
            preprocess_desc += f" + tophat(r={tophat_radius})"
        log_preprocessing(logger, preprocess_desc)

        # Detect tubercles with configurable parameters
        threshold = get_param("threshold", args.threshold, 0.05)
        min_circularity = get_param("min_circularity", args.circularity, 0.5)
        min_diameter = get_param("min_diameter_um", args.min_diameter, 2.0)
        max_diameter = get_param("max_diameter_um", args.max_diameter, 10.0)
        edge_margin = get_param("edge_margin_px", args.edge_margin, 10)

        detect_kwargs = {
            "min_diameter_um": min_diameter,
            "max_diameter_um": max_diameter,
            "threshold": threshold,
            "min_circularity": min_circularity,
            "edge_margin_px": edge_margin,
            "method": args.method,
            "refine_ellipse": args.refine_ellipse,
            "max_eccentricity": args.max_eccentricity,
        }
        # Add optional sigma overrides (from CLI or profile)
        min_sigma = args.min_sigma
        max_sigma = args.max_sigma
        if min_sigma is None and profile and profile.min_sigma:
            min_sigma = profile.min_sigma
        if max_sigma is None and profile and profile.max_sigma:
            max_sigma = profile.max_sigma
        if min_sigma is not None:
            detect_kwargs["min_sigma_override"] = min_sigma
        if max_sigma is not None:
            detect_kwargs["max_sigma_override"] = max_sigma

        # Add lattice parameters if using lattice method
        if args.method == "lattice":
            lattice_params = {}
            if args.seed_threshold is not None:
                lattice_params["seed_threshold"] = args.seed_threshold
            if args.min_seeds is not None:
                lattice_params["min_seeds"] = args.min_seeds
            if args.lattice_regularity is not None:
                lattice_params["min_regularity"] = args.lattice_regularity
            if lattice_params:
                detect_kwargs["lattice_params"] = lattice_params

        tubercles = detect_tubercles(
            preprocessed,
            calibration,
            **detect_kwargs,
        )
        log_detection(logger, len(tubercles))

        if len(tubercles) < 10:
            log_warning(logger, f"Few tubercles detected ({len(tubercles)}) - results may be unreliable")

        # Measure metrics
        result = measure_metrics(
            tubercles, calibration, str(image_path),
            graph_type=args.neighbor_graph,
            max_distance_factor=args.max_edge_factor,
            spacing_method=args.spacing_method,
        )
        log_measurement(
            logger,
            result.mean_diameter_um,
            result.std_diameter_um,
            result.mean_space_um,
            result.std_space_um,
        )
        log_classification(logger, result.suggested_genus, result.classification_confidence)

        # Write outputs
        base_name = image_path.stem
        csv_paths = write_all_outputs(result, session_dir, base_name)

        # Generate visualizations
        if not args.no_viz:
            viz_path = session_dir / f"{base_name}_detection.png"
            create_combined_figure(
                image, result, viz_path,
                label_mode=args.label_mode,
                calibration_um_per_px=calibration.um_per_pixel,
                graph_type=args.neighbor_graph,
            )

            if args.show_preprocessing:
                prep_path = session_dir / f"{base_name}_preprocessing.png"
                create_preprocessing_figure(intermediates, prep_path)

        log_output(logger, str(session_dir))

        # Print summary table
        table = Table(title="Measurement Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Tubercles Detected", str(result.n_tubercles))
        table.add_row("Tubercle Diameter", f"{result.mean_diameter_um:.2f} ± {result.std_diameter_um:.2f} µm")
        table.add_row("Intertubercular Space", f"{result.mean_space_um:.2f} ± {result.std_space_um:.2f} µm")
        table.add_row("Suggested Genus", f"{result.suggested_genus} ({result.classification_confidence})")
        table.add_row("Output Directory", str(session_dir))

        console.print(table)

        return 0

    except Exception as e:
        log_error(logger, f"Error processing image: {e}")
        if args.verbose:
            console.print_exception()
        return 1


def process_batch(args: argparse.Namespace) -> int:
    """Process multiple images."""
    # Create session directory
    session_dir = create_session_dir(args.output)
    logger = setup_logger(session_dir)

    image_dir = args.directory
    if not image_dir.exists():
        log_error(logger, f"Directory not found: {image_dir}")
        return 1

    # Find all TIFF images
    image_files = list(image_dir.glob("*.tif")) + list(image_dir.glob("*.tiff"))
    if not image_files:
        log_error(logger, f"No TIFF images found in {image_dir}")
        return 1

    console.print(f"[bold]Found {len(image_files)} images to process[/bold]")

    results = []
    batch_csv = session_dir / "batch_results.csv"

    for image_path in image_files:
        log_image_start(logger, str(image_path))

        try:
            # Load image
            image = load_image(image_path)

            # Calibration
            if args.scale_bar_um and args.scale_bar_px:
                calibration = calibrate_manual(args.scale_bar_um, args.scale_bar_px)
            else:
                calibration = estimate_calibration_700x(image.shape[1])

            # Preprocess
            preprocessed, intermediates = preprocess_pipeline(image)

            # Detect tubercles
            tubercles = detect_tubercles(
                preprocessed,
                calibration,
                min_diameter_um=args.min_diameter,
                max_diameter_um=args.max_diameter,
                threshold=args.threshold,
                min_circularity=args.circularity,
            )

            # Measure metrics
            result = measure_metrics(tubercles, calibration, str(image_path))
            results.append(result)

            log_detection(logger, len(tubercles))
            log_measurement(
                logger,
                result.mean_diameter_um,
                result.std_diameter_um,
                result.mean_space_um,
                result.std_space_um,
            )
            log_classification(logger, result.suggested_genus, result.classification_confidence)

            # Append to batch CSV
            append_to_batch_csv(result, batch_csv)

            # Generate visualization
            if not args.no_viz:
                base_name = image_path.stem
                viz_path = session_dir / f"{base_name}_detection.png"
                create_combined_figure(image, result, viz_path)

        except Exception as e:
            log_error(logger, f"Error processing {image_path}: {e}")
            if args.verbose:
                console.print_exception()
            continue

    # Generate scatter plot
    if args.scatter and results:
        scatter_path = session_dir / "scatter_plot.png"
        create_scatter_plot(results, scatter_path)

    log_output(logger, str(session_dir))

    # Print summary table
    table = Table(title=f"Batch Results ({len(results)}/{len(image_files)} processed)")
    table.add_column("Image", style="cyan")
    table.add_column("n", style="white")
    table.add_column("Diameter (µm)", style="green")
    table.add_column("Spacing (µm)", style="green")
    table.add_column("Genus", style="yellow")

    for r in results:
        table.add_row(
            Path(r.image_path).stem[:30],
            str(r.n_tubercles),
            f"{r.mean_diameter_um:.2f} ± {r.std_diameter_um:.2f}",
            f"{r.mean_space_um:.2f} ± {r.std_space_um:.2f}",
            r.suggested_genus or "Unknown",
        )

    console.print(table)
    console.print(f"\n[bold]Results saved to:[/bold] {session_dir}")

    return 0


def run_benchmark(args: argparse.Namespace) -> int:
    """Compare measurements against expected values from literature."""
    test_dir = args.test_dir

    if not test_dir.exists():
        console.print(f"[red]Test directory not found: {test_dir}[/red]")
        return 1

    # Expected values from test_cases.md
    test_cases = [
        ("P1_Fig1_Lepidotes_elvensis_4.78um.tif", 4.78, 4.57, 0.5, 0.7),
        ("P1_Fig2_Polypterus_bichir_2.63um.tif", 2.63, 6.19, 0.5, 0.7),
        ("P1_Fig3_Lepisosteus_osseus_3.79um.tif", 3.79, 3.14, 0.5, 0.7),
        ("P1_Fig4_Atractosteus_simplex_7.07um.tif", 7.07, 2.61, 0.5, 0.7),
        ("P1_Fig5_Lepisosteidae_indet_Portugal_3.82um.tif", 3.82, 3.82, 0.5, 0.7),
        ("P1_Fig6_Lepisosteidae_indet_Bolivia_4.50um.tif", 4.50, 4.40, 0.5, 0.7),
        ("P2_Pl1_Fig1a_Lepisosteus_platostomus_5.38um.tif", 5.38, 3.59, 0.5, 0.7),
        ("P2_Pl1_Fig1b_Polypterus_ornatipinnis_2.81um.tif", 2.81, 5.97, 0.5, 0.7),
        ("P3_Fig4_Obaichthys_laevis_5.0um.tif", 5.0, 4.67, 0.5, 0.7),
        ("P3_Fig5_Obaichthys_decoratus_5.0um.tif", 5.0, 4.67, 0.5, 0.7),
    ]

    console.print(Panel.fit("[bold]Benchmark: Comparing Measurements vs Literature Values[/bold]"))

    passed = 0
    failed = 0
    skipped = 0

    table = Table(title="Benchmark Results (D=diameter, S=spacing in µm)")
    table.add_column("Test Case", style="cyan")
    table.add_column("Expected D", style="white")
    table.add_column("Measured D", style="white")
    table.add_column("Expected S", style="white")
    table.add_column("Measured S", style="white")
    table.add_column("Status", style="bold")

    for filename, exp_diam, exp_space, diam_tol, space_tol in test_cases:
        image_path = test_dir / filename

        if not image_path.exists():
            table.add_row(filename[:35], "-", "-", "-", "-", "[yellow]SKIPPED[/yellow]")
            skipped += 1
            continue

        try:
            # Process image with default parameters
            result, _, _ = process_image(image_path)

            # Check tolerances
            diam_ok = abs(result.mean_diameter_um - exp_diam) <= diam_tol
            space_ok = abs(result.mean_space_um - exp_space) <= space_tol

            if diam_ok and space_ok:
                status = "[green]PASS[/green]"
                passed += 1
            else:
                status = "[red]FAIL[/red]"
                failed += 1

            table.add_row(
                filename[:35],
                f"{exp_diam:.2f}",
                f"{result.mean_diameter_um:.2f}",
                f"{exp_space:.2f}",
                f"{result.mean_space_um:.2f}",
                status,
            )

        except Exception as e:
            table.add_row(filename[:35], "-", "-", "-", "-", f"[red]ERROR: {str(e)[:20]}[/red]")
            failed += 1

    console.print(table)

    # Summary
    total = passed + failed + skipped
    console.print(f"\n[bold]Summary:[/bold] {passed}/{total} passed, {failed} failed, {skipped} skipped")

    if failed == 0 and skipped == 0:
        console.print("[bold green]All benchmarks within tolerance![/bold green]")
        return 0
    else:
        return 1


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "process":
        return process_single_image(args)
    elif args.command == "batch":
        return process_batch(args)
    elif args.command == "benchmark":
        return run_benchmark(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
