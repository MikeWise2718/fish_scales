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
        help="API key (or use GEMINI_API_KEY/ANTHROPIC_API_KEY env var)",
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
        console.print(
            "[yellow]OpenRouter provider not yet implemented.[/yellow] "
            "See Phase 3 of the implementation plan.",
        )
        sys.exit(1)

    else:
        console.print(f"[red]Unknown provider:[/red] {provider_name}")
        sys.exit(1)


def check_ui_available(ui_url: str) -> bool:
    """Check if the fish-scale-ui is running."""
    import httpx

    try:
        resp = httpx.get(f"{ui_url}/api/mcp/state", timeout=5)
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
            "[yellow]openrouter[/yellow] - OpenRouter (not yet implemented)\n"
            "  Env var: OPENROUTER_API_KEY",
            title="Available Providers",
        )
    )


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "providers":
        cmd_providers(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
