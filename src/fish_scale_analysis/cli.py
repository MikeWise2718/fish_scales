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
        type=Path,
        help="Path to TIFF image file",
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
        default=2.0,
        help="Minimum expected tubercle diameter in µm (default: 2.0)",
    )
    process_parser.add_argument(
        "--max-diameter",
        type=float,
        default=10.0,
        help="Maximum expected tubercle diameter in µm (default: 10.0)",
    )
    process_parser.add_argument(
        "--threshold",
        type=float,
        default=0.05,
        help="Blob detection threshold, lower=more sensitive (default: 0.05)",
    )
    process_parser.add_argument(
        "--circularity",
        type=float,
        default=0.5,
        help="Minimum circularity filter 0-1 (default: 0.5)",
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

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Run validation against test images",
        formatter_class=RichHelpFormatter,
    )
    validate_parser.add_argument(
        "--test-dir",
        type=Path,
        default=Path("test_images"),
        help="Directory containing test images (default: ./test_images)",
    )
    validate_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    return parser


def process_single_image(args: argparse.Namespace) -> int:
    """Process a single image."""
    # Create session directory
    session_dir = create_session_dir(args.output)
    logger = setup_logger(session_dir)

    image_path = args.image
    if not image_path.exists():
        log_error(logger, f"Image not found: {image_path}")
        return 1

    log_image_start(logger, str(image_path))

    try:
        # Load image
        image = load_image(image_path)

        # Calibration
        if args.scale_bar_um and args.scale_bar_px:
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

        # Preprocess
        preprocessed, intermediates = preprocess_pipeline(image)
        log_preprocessing(logger, "CLAHE + Gaussian blur")

        # Detect tubercles
        tubercles = detect_tubercles(
            preprocessed,
            calibration,
            min_diameter_um=args.min_diameter,
            max_diameter_um=args.max_diameter,
            threshold=args.threshold,
            min_circularity=args.circularity,
        )
        log_detection(logger, len(tubercles))

        if len(tubercles) < 10:
            log_warning(logger, f"Few tubercles detected ({len(tubercles)}) - results may be unreliable")

        # Measure metrics
        result = measure_metrics(tubercles, calibration, str(image_path))
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
            create_combined_figure(image, result, viz_path)

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


def run_validation(args: argparse.Namespace) -> int:
    """Run validation against test images with known expected values."""
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

    console.print(Panel.fit("[bold]Running Validation Tests[/bold]"))

    passed = 0
    failed = 0
    skipped = 0

    table = Table(title="Validation Results")
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
        console.print("[bold green]All tests passed![/bold green]")
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
    elif args.command == "validate":
        return run_validation(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
