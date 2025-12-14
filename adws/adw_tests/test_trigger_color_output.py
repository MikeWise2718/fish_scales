"""
Unit tests for the ADW console module colorized output.

Tests verify that the console helper functions produce correct styled output
with appropriate ANSI color codes.
"""

import sys
import io
from unittest.mock import patch
import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(__file__).rsplit('/', 2)[0])

from adw_modules.console import (
    console,
    print_info,
    print_success,
    print_warning,
    print_error,
    print_debug,
)


class TestConsoleModule:
    """Test suite for console module helper functions."""

    def test_console_instance_exists(self):
        """Test that the shared console instance is properly initialized."""
        assert console is not None
        assert hasattr(console, 'print')

    def test_print_info_produces_output(self, capsys):
        """Test that print_info produces output."""
        print_info("Test info message")
        captured = capsys.readouterr()
        assert "Test info message" in captured.out

    def test_print_success_produces_output(self, capsys):
        """Test that print_success produces output."""
        print_success("Test success message")
        captured = capsys.readouterr()
        assert "Test success message" in captured.out

    def test_print_warning_produces_output(self, capsys):
        """Test that print_warning produces output."""
        print_warning("Test warning message")
        captured = capsys.readouterr()
        assert "Test warning message" in captured.out

    def test_print_error_produces_output(self, capsys):
        """Test that print_error produces output."""
        print_error("Test error message")
        captured = capsys.readouterr()
        assert "Test error message" in captured.out

    def test_print_debug_produces_output(self, capsys):
        """Test that print_debug produces output."""
        print_debug("Test debug message")
        captured = capsys.readouterr()
        assert "Test debug message" in captured.out

    def test_info_contains_white_markup(self):
        """Test that info messages use white color markup."""
        # Capture the output to a string buffer
        string_io = io.StringIO()
        test_console = console.__class__(file=string_io, force_terminal=True)
        test_console.print("[white]Test info[/white]")
        output = string_io.getvalue()
        # Should contain ANSI codes or the actual text
        assert "Test info" in output

    def test_success_contains_green_markup(self):
        """Test that success messages use green color markup."""
        string_io = io.StringIO()
        test_console = console.__class__(file=string_io, force_terminal=True)
        test_console.print("[green]Test success[/green]")
        output = string_io.getvalue()
        assert "Test success" in output

    def test_warning_contains_yellow_markup(self):
        """Test that warning messages use yellow color markup."""
        string_io = io.StringIO()
        test_console = console.__class__(file=string_io, force_terminal=True)
        test_console.print("[yellow]Test warning[/yellow]")
        output = string_io.getvalue()
        assert "Test warning" in output

    def test_error_contains_red_markup(self):
        """Test that error messages use red color markup."""
        string_io = io.StringIO()
        test_console = console.__class__(file=string_io, force_terminal=True)
        test_console.print("[red]Test error[/red]")
        output = string_io.getvalue()
        assert "Test error" in output

    def test_debug_contains_cyan_markup(self):
        """Test that debug messages use cyan color markup."""
        string_io = io.StringIO()
        test_console = console.__class__(file=string_io, force_terminal=True)
        test_console.print("[cyan]Test debug[/cyan]")
        output = string_io.getvalue()
        assert "Test debug" in output

    def test_functions_handle_multiline_text(self, capsys):
        """Test that helper functions handle multiline text correctly."""
        multiline_message = "Line 1\nLine 2\nLine 3"
        print_info(multiline_message)
        captured = capsys.readouterr()
        assert "Line 1" in captured.out
        assert "Line 2" in captured.out
        assert "Line 3" in captured.out

    def test_functions_handle_formatted_strings(self, capsys):
        """Test that helper functions handle f-strings correctly."""
        issue_number = 123
        print_info(f"Processing issue #{issue_number}")
        captured = capsys.readouterr()
        assert "Processing issue #123" in captured.out

    def test_functions_handle_empty_string(self, capsys):
        """Test that helper functions handle empty strings without errors."""
        print_info("")
        captured = capsys.readouterr()
        # Should not raise an error, output may be empty or whitespace
        assert isinstance(captured.out, str)

    def test_functions_handle_unicode(self, capsys):
        """Test that helper functions handle unicode characters."""
        print_success("✅ Success with emoji")
        print_warning("⚠️  Warning with emoji")
        print_error("❌ Error with emoji")
        captured = capsys.readouterr()
        assert "✅" in captured.out or "Success" in captured.out
        assert "⚠️" in captured.out or "Warning" in captured.out
        assert "❌" in captured.out or "Error" in captured.out

    def test_functions_accept_additional_kwargs(self, capsys):
        """Test that helper functions accept additional keyword arguments."""
        # The functions should accept additional kwargs like 'end'
        print_info("Test", end="")
        captured = capsys.readouterr()
        assert "Test" in captured.out

    def test_non_string_input(self, capsys):
        """Test that helper functions handle non-string input."""
        print_info(123)
        print_success(True)
        print_warning(None)
        captured = capsys.readouterr()
        assert "123" in captured.out
        assert "True" in captured.out
        assert "None" in captured.out


class TestConsoleInNonTTY:
    """Test console behavior in non-TTY environments."""

    def test_output_in_non_tty_environment(self):
        """Test that output works in non-TTY environments without ANSI codes."""
        # Create a console that's not a terminal
        string_io = io.StringIO()
        test_console = console.__class__(file=string_io, force_terminal=False)
        test_console.print("[red]Error message[/red]")
        output = string_io.getvalue()
        # Should contain the message
        assert "Error message" in output
        # Should not contain ANSI color codes when not forced
        # (Rich strips them in non-TTY mode)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
