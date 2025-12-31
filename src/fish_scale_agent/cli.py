"""CLI for the fish scale detection agent."""

import argparse
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="fish-scale-agent",
        description="LLM agent for automated tubercle detection in fish scale images",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run the agent on an image",
    )
    run_parser.add_argument(
        "image",
        nargs="?",
        help="Path to image file (optional if already loaded in UI)",
    )
    run_parser.add_argument(
        "--provider",
        choices=["claude", "gemini", "openrouter"],
        default="claude",
        help="LLM provider (default: claude)",
    )
    run_parser.add_argument(
        "--model",
        help="Specific model name (default depends on provider)",
    )
    run_parser.add_argument(
        "--api-key",
        help="API key (or use ANTHROPIC_API_KEY/GEMINI_API_KEY/OPENROUTER_API_KEY env var)",
    )
    run_parser.add_argument(
        "--calibration",
        type=float,
        help="Calibration in micrometers per pixel (optional if already set)",
    )
    run_parser.add_argument(
        "--max-iterations",
        type=int,
        default=20,
        help="Maximum agent iterations (default: 20)",
    )
    run_parser.add_argument(
        "--ui-url",
        default="http://localhost:5010",
        help="URL of fish-scale-ui (default: http://localhost:5010)",
    )
    run_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    # List providers command
    subparsers.add_parser(
        "providers",
        help="List available LLM providers",
    )

    # Optimize command
    optimize_parser = subparsers.add_parser(
        "optimize",
        help="Optimize extraction parameters using LLM agent",
    )
    optimize_parser.add_argument(
        "image",
        help="Path to image file",
    )
    optimize_parser.add_argument(
        "--calibration",
        type=float,
        required=True,
        help="Calibration in micrometers per pixel (required)",
    )
    optimize_parser.add_argument(
        "--provider",
        choices=["claude", "gemini", "openrouter"],
        default="claude",
        help="LLM provider (default: claude)",
    )
    optimize_parser.add_argument(
        "--model",
        help="Specific model name (default depends on provider)",
    )
    optimize_parser.add_argument(
        "--api-key",
        help="API key (or use ANTHROPIC_API_KEY/GEMINI_API_KEY/OPENROUTER_API_KEY env var)",
    )
    optimize_parser.add_argument(
        "--profile",
        default="default",
        help="Starting parameter profile (default: default)",
    )
    optimize_parser.add_argument(
        "--target-score",
        type=float,
        default=0.7,
        help="Target hexagonalness score (default: 0.7)",
    )
    optimize_parser.add_argument(
        "--max-iterations",
        type=int,
        default=10,
        help="Maximum optimization iterations (default: 10)",
    )
    optimize_parser.add_argument(
        "--ui-url",
        default="http://localhost:5010",
        help="URL of fish-scale-ui (default: http://localhost:5010)",
    )
    optimize_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    return parser


def get_provider(provider_name: str, model: str | None, api_key: str | None):
    """Create and return an LLM provider instance."""
    if provider_name == "claude":
        from .providers.claude import ClaudeAgentProvider

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            console.print(
                "[red]Error:[/red] Anthropic API key required. "
                "Set ANTHROPIC_API_KEY env var or use --api-key",
                style="bold",
            )
            sys.exit(1)

        return ClaudeAgentProvider(
            api_key=key,
            model=model or "claude-sonnet-4-20250514",
        )

    elif provider_name == "gemini":
        from .providers.gemini import GeminiAgentProvider

        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            console.print(
                "[red]Error:[/red] Gemini API key required. "
                "Set GEMINI_API_KEY env var or use --api-key",
                style="bold",
            )
            sys.exit(1)

        return GeminiAgentProvider(
            api_key=key,
            model=model or "gemini-2.0-flash",
        )

    elif provider_name == "openrouter":
        from .providers.openrouter import OpenRouterAgentProvider

        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            console.print(
                "[red]Error:[/red] OpenRouter API key required. "
                "Set OPENROUTER_API_KEY env var or use --api-key",
                style="bold",
            )
            sys.exit(1)

        return OpenRouterAgentProvider(
            api_key=key,
            model=model or "anthropic/claude-sonnet-4",
        )

    else:
        console.print(f"[red]Unknown provider:[/red] {provider_name}")
        sys.exit(1)


def check_ui_available(ui_url: str) -> bool:
    """Check if the fish-scale-ui is running."""
    import httpx

    try:
        resp = httpx.get(f"{ui_url}/api/tools/state", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def cmd_run(args):
    """Run the agent on an image."""
    from .runner import TubercleDetectionAgent

    # Check if UI is available
    if not check_ui_available(args.ui_url):
        console.print(
            Panel(
                f"[red]fish-scale-ui not available at {args.ui_url}[/red]\n\n"
                "Please start the UI first:\n"
                "  [cyan]uv run fish-scale-ui[/cyan]",
                title="Connection Error",
            )
        )
        sys.exit(1)

    # Validate image path if provided
    image_path = None
    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            console.print(f"[red]Error:[/red] Image not found: {image_path}")
            sys.exit(1)

    # Get provider
    provider = get_provider(args.provider, args.model, args.api_key)

    console.print(
        Panel(
            f"Provider: [cyan]{provider.provider_name}[/cyan]\n"
            f"Model: [cyan]{provider.model_name}[/cyan]\n"
            f"UI: [cyan]{args.ui_url}[/cyan]\n"
            f"Max iterations: [cyan]{args.max_iterations}[/cyan]"
            + (f"\nImage: [cyan]{image_path}[/cyan]" if image_path else "")
            + (f"\nCalibration: [cyan]{args.calibration} um/px[/cyan]" if args.calibration else ""),
            title="Fish Scale Agent",
        )
    )

    # Create agent
    agent = TubercleDetectionAgent(
        provider=provider,
        ui_base_url=args.ui_url,
        verbose=args.verbose,
    )

    # Run agent
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True,
        ) as progress:
            task = progress.add_task("Running agent...", total=None)

            result = agent.run_sync(
                image_path=image_path,
                calibration_um_per_px=args.calibration,
                max_iterations=args.max_iterations,
            )

            progress.update(task, description="Complete!")

        console.print("\n[green]Agent Result:[/green]\n")
        console.print(Panel(result, title="Final Response"))

    except KeyboardInterrupt:
        console.print("\n[yellow]Agent interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        agent.close()


def cmd_providers(args):
    """List available providers."""
    console.print(
        Panel(
            "[green]claude[/green] - Anthropic Claude (default: claude-sonnet-4-20250514) [DEFAULT]\n"
            "  Env var: ANTHROPIC_API_KEY\n\n"
            "[green]gemini[/green] - Google Gemini (default: gemini-2.0-flash)\n"
            "  Env var: GEMINI_API_KEY\n\n"
            "[green]openrouter[/green] - OpenRouter (default: anthropic/claude-sonnet-4)\n"
            "  Env var: OPENROUTER_API_KEY\n"
            "  Models: anthropic/claude-*, openai/gpt-4o*, google/gemini-*, meta-llama/*, etc.\n"
            "  See https://openrouter.ai/docs#models for full list",
            title="Available Providers",
        )
    )


def cmd_optimize(args):
    """Optimize extraction parameters using LLM agent."""
    from .extraction_optimizer import ExtractionOptimizer, OptimizationState

    # Check if UI is available
    if not check_ui_available(args.ui_url):
        console.print(
            Panel(
                f"[red]fish-scale-ui not available at {args.ui_url}[/red]\n\n"
                "Please start the UI first:\n"
                "  [cyan]uv run fish-scale-ui[/cyan]",
                title="Connection Error",
            )
        )
        sys.exit(1)

    # Validate image path
    image_path = Path(args.image)
    if not image_path.exists():
        console.print(f"[red]Error:[/red] Image not found: {image_path}")
        sys.exit(1)

    # Get provider
    provider = get_provider(args.provider, args.model, getattr(args, 'api_key', None))

    # Print header
    console.print()
    console.print("[bold]Fish Scale Extraction Optimizer[/bold]")
    console.print("=" * 34)
    console.print(f"Image: [cyan]{image_path.name}[/cyan]")
    console.print(f"Provider: [cyan]{args.provider}[/cyan] ({provider.model_name})")
    console.print(f"Starting profile: [cyan]{args.profile}[/cyan]")
    console.print(f"Target hexagonalness: [cyan]{args.target_score:.2f}[/cyan]")
    console.print()

    # Track last printed iteration to avoid duplicates
    last_printed_iteration = [0]

    def on_iteration(state: OptimizationState):
        """Callback for each optimization iteration."""
        if state.iteration <= last_printed_iteration[0]:
            return  # Already printed this iteration
        last_printed_iteration[0] = state.iteration

        hex_score = state.current_metrics.get("hexagonalness", 0)
        n_tubercles = state.current_metrics.get("n_tubercles", 0)

        # Print iteration progress - use plain print with flush for subprocess capture
        # Rich console output may be buffered, so we print plain text for parsing
        print(
            f"Iteration {state.iteration}/{args.max_iterations}: "
            f"Hexagonalness: {hex_score:.3f}, "
            f"Tubercles: {n_tubercles}",
            flush=True
        )

        # Note if this is the new best
        if state.iteration == state.best_iteration and state.iteration > 1:
            print("  ^ New best result", flush=True)

    # Create optimizer
    optimizer = ExtractionOptimizer(
        provider=provider,
        ui_base_url=args.ui_url,
        verbose=args.verbose,
    )

    # Run optimization
    try:
        console.print("[dim]Running initial extraction...[/dim]")

        result = optimizer.optimize_sync(
            image_path=str(image_path.resolve()),
            calibration=args.calibration,
            starting_profile=args.profile,
            target_hexagonalness=args.target_score,
            max_iterations=args.max_iterations,
            on_iteration=on_iteration,
        )

        # Print final summary
        console.print()
        console.print("[bold]Optimization Complete[/bold]")
        console.print("-" * 21)
        console.print(f"Best result: Iteration {result.best_iteration}")
        console.print(f"  Hexagonalness: [green]{result.best_metrics.get('hexagonalness', 0):.3f}[/green]")
        console.print(f"  Tubercles: [cyan]{result.best_metrics.get('n_tubercles', 0)}[/cyan]")

        mean_diam = result.best_metrics.get("mean_diameter_um", 0)
        mean_space = result.best_metrics.get("mean_space_um", 0)
        if mean_diam:
            console.print(f"  Mean diameter: [cyan]{mean_diam:.1f} um[/cyan]")
        if mean_space:
            console.print(f"  Mean spacing: [cyan]{mean_space:.1f} um[/cyan]")

        console.print()
        console.print("[bold]Optimal parameters:[/bold]")
        key_params = [
            "threshold", "min_diameter_um", "max_diameter_um",
            "min_circularity", "clahe_clip", "blur_sigma", "neighbor_graph"
        ]
        for key in key_params:
            if key in result.best_params:
                val = result.best_params[key]
                if isinstance(val, float):
                    console.print(f"  {key}: [cyan]{val:.3f}[/cyan]")
                else:
                    console.print(f"  {key}: [cyan]{val}[/cyan]")

        # Print usage stats if available
        if hasattr(provider, "get_usage"):
            usage = provider.get_usage()
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cost = usage.get("cost_usd", 0)
            estimated = usage.get("cost_estimated", False)

            console.print()
            cost_str = f"~${cost:.2f}" if estimated else f"${cost:.2f}"
            console.print(
                f"[dim]Usage: {input_tokens:,} input + {output_tokens:,} output tokens "
                f"({cost_str})[/dim]"
            )

    except KeyboardInterrupt:
        console.print("\n[yellow]Optimization interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Error:[/red] {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    finally:
        optimizer.close()


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "providers":
        cmd_providers(args)
    elif args.command == "optimize":
        cmd_optimize(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
