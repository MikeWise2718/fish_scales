"""
Shared Rich Console module for colorized output in ADW trigger scripts.

This module provides a centralized Rich Console instance and helper functions
for consistent, colorized console output across all ADW trigger scripts.

Color Scheme:
- INFO: White/default (informational messages)
- SUCCESS: Green (successful operations)
- WARNING: Yellow (warning messages)
- ERROR: Red (error messages)
- DEBUG: Cyan (debug messages)
"""

from rich.console import Console
from typing import Any

# Create a shared Console instance
# Rich automatically handles TTY detection and adjusts output accordingly
console = Console()


def print_info(message: Any, **kwargs) -> None:
    """Print an informational message in white/default color.

    Args:
        message: The message to print (can be string or any printable object)
        **kwargs: Additional arguments to pass to console.print()

    Example:
        print_info("Starting workflow process")
        print_info(f"Processing issue #{issue_number}")
    """
    console.print(f"[white]{message}[/white]", **kwargs)


def print_success(message: Any, **kwargs) -> None:
    """Print a success message in green.

    Args:
        message: The message to print (can be string or any printable object)
        **kwargs: Additional arguments to pass to console.print()

    Example:
        print_success("Workflow completed successfully")
        print_success(f"✅ Issue #{issue_number} processed")
    """
    console.print(f"[green]{message}[/green]", **kwargs)


def print_warning(message: Any, **kwargs) -> None:
    """Print a warning message in yellow.

    Args:
        message: The message to print (can be string or any printable object)
        **kwargs: Additional arguments to pass to console.print()

    Example:
        print_warning("Workflow took longer than expected")
        print_warning(f"⚠️  Rate limit approaching")
    """
    console.print(f"[yellow]{message}[/yellow]", **kwargs)


def print_error(message: Any, **kwargs) -> None:
    """Print an error message in red.

    Args:
        message: The message to print (can be string or any printable object)
        **kwargs: Additional arguments to pass to console.print()

    Example:
        print_error("Failed to process workflow")
        print_error(f"❌ Error: {error_message}")
    """
    console.print(f"[red]{message}[/red]", **kwargs)


def print_debug(message: Any, **kwargs) -> None:
    """Print a debug message in cyan.

    Args:
        message: The message to print (can be string or any printable object)
        **kwargs: Additional arguments to pass to console.print()

    Example:
        print_debug("Variable state: active")
        print_debug(f"Command: {' '.join(cmd)}")
    """
    console.print(f"[cyan]{message}[/cyan]", **kwargs)


def print_status(message: Any, **kwargs) -> None:
    """Print a status message in bold blue/cyan for system state indicators.

    Args:
        message: The message to print (can be string or any printable object)
        **kwargs: Additional arguments to pass to console.print()

    Example:
        print_status("BUSY - Processing issue #123")
        print_status("IDLE - Waiting for new issues to process")
    """
    console.print(f"[bold cyan]STATUS: {message}[/bold cyan]", **kwargs)
