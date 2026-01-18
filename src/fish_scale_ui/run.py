"""Entry point for Fish Scale Measurement UI."""

import argparse
import os
import webbrowser
import threading
import time
from pathlib import Path


def main():
    """Run the Fish Scale UI application."""
    parser = argparse.ArgumentParser(
        description='Fish Scale Measurement UI',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-d', '--image-dir',
        type=str,
        default='test_images',
        help='Directory to browse for images'
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        default=5010,
        help='Port to run the server on'
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not automatically open browser'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Run in debug mode'
    )

    args = parser.parse_args()

    # Resolve image directory to absolute path
    image_dir = Path(args.image_dir).resolve()
    if not image_dir.exists():
        print(f"Warning: Image directory '{image_dir}' does not exist. Creating it.")
        image_dir.mkdir(parents=True, exist_ok=True)

    from fish_scale_ui.app import create_app

    app = create_app(config={
        'IMAGE_DIR': image_dir,
    })

    # Open browser after short delay
    if not args.no_browser:
        def open_browser():
            time.sleep(1)
            webbrowser.open(f'http://127.0.0.1:{args.port}')

        threading.Thread(target=open_browser, daemon=True).start()

    # Get version info
    from fish_scale_ui import __version__, __version_date__
    from datetime import datetime, timezone
    from rich.console import Console
    import subprocess as sp

    console = Console()

    # Get commit datetime in UTC
    build_datetime_utc = "unknown"
    try:
        result = sp.run(
            ['git', 'log', '-1', '--format=%cI'],
            capture_output=True, text=True, timeout=5,
            cwd=Path(__file__).parent.parent.parent
        )
        if result.returncode == 0:
            commit_dt = datetime.fromisoformat(result.stdout.strip())
            commit_utc = commit_dt.astimezone(timezone.utc)
            build_datetime_utc = commit_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        pass

    console.print("[bold cyan]Starting Fish Scale Measurement UI...[/bold cyan]")
    console.print(f"  [dim]Version:[/dim] [cyan]{__version__}[/cyan] ({__version_date__})")
    console.print(f"  [dim]Build:[/dim]   [cyan]{build_datetime_utc}[/cyan]")
    console.print(f"  [dim]Image directory:[/dim] {image_dir}")

    # Show AI provider availability
    providers_configured = []
    providers_not_configured = []

    if os.environ.get('ANTHROPIC_API_KEY'):
        providers_configured.append("Claude")
    else:
        providers_not_configured.append("Claude")

    if os.environ.get('GEMINI_API_KEY'):
        providers_configured.append("Gemini")
    else:
        providers_not_configured.append("Gemini")

    if os.environ.get('OPENROUTER_API_KEY'):
        providers_configured.append("OpenRouter")
    else:
        providers_not_configured.append("OpenRouter")

    # Ollama requires explicit OLLAMA_HOST to be considered configured
    ollama_host = os.environ.get('OLLAMA_HOST')
    if ollama_host:
        providers_configured.append(f"Ollama ({ollama_host})")
    else:
        providers_not_configured.append("Ollama")

    if providers_configured:
        console.print(f"  [dim]AI Providers:[/dim] [green]{', '.join(providers_configured)}[/green]")
    if providers_not_configured:
        console.print(f"  [dim]AI Providers (not configured):[/dim] [yellow]{', '.join(providers_not_configured)}[/yellow]")

    # Debug: Show environment variable configuration
    agent_tabs_env = os.environ.get('FISH_SCALE_AGENT_TABS', '')
    fish_user_env = os.environ.get('FISH_SCALE_USER', '')
    env_value = repr(agent_tabs_env) if agent_tabs_env else '[dim](not set)[/dim]'
    console.print(f"  [dim]FISH_SCALE_AGENT_TABS:[/dim] {env_value}")
    user_value = repr(fish_user_env) if fish_user_env else '[dim](not set)[/dim]'
    console.print(f"  [dim]FISH_SCALE_USER:[/dim] {user_value}")

    from fish_scale_ui.app import get_agent_tabs_config
    agent_tabs = get_agent_tabs_config()
    ext_status = "[green]True[/green]" if agent_tabs['extraction'] else "[dim]False[/dim]"
    edit_status = "[green]True[/green]" if agent_tabs['editing'] else "[dim]False[/dim]"
    console.print(f"  [dim]Agent tabs enabled:[/dim] extraction={ext_status}, editing={edit_status}")

    console.print(f"[bold]Opening browser at[/bold] [link=http://127.0.0.1:{args.port}]http://127.0.0.1:{args.port}[/link]")
    console.print("[dim]Press Ctrl+C to stop the server.[/dim]")

    app.run(host='127.0.0.1', port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
