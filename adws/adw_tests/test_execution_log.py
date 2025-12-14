#!/usr/bin/env python3
"""Tests for execution logging and configuration modules.

Tests cover:
- adw_config.py: Settings loading, path resolution, caching
- execution_log.py: Log entry creation, file writing, subprocess tracking

Run with: uv run python adw_tests/test_execution_log.py
"""

import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adw_modules import adw_config
from adw_modules.execution_log import (
    log_execution_start,
    log_execution_end,
    track_subprocess_start,
    track_subprocess_end,
    track_agent_execution,
    get_files_changed_since,
    get_file_info,
    get_file_info_with_diff,
    _get_iso_timestamp,
    _sanitize_env_vars,
    _reset_agent_metrics,
    _get_agent_metrics,
    FileInfo,
    FilesSummary,
    SubprocessInvocation,
    StartLogEntry,
    EndLogEntry,
)


class TestRunner:
    """Simple test runner with pass/fail tracking."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def run_test(self, name: str, test_func):
        """Run a single test and track results."""
        try:
            result = test_func()
            if result:
                print(f"  ✅ {name}")
                self.passed += 1
            else:
                print(f"  ❌ {name}")
                self.failed += 1
        except Exception as e:
            print(f"  ❌ {name} - Exception: {e}")
            self.errors.append((name, str(e)))
            self.failed += 1

    def summary(self):
        """Print test summary."""
        total = self.passed + self.failed
        print(f"\n{'=' * 50}")
        print(f"Tests: {total} | Passed: {self.passed} | Failed: {self.failed}")
        if self.errors:
            print("\nErrors:")
            for name, error in self.errors:
                print(f"  - {name}: {error}")
        return self.failed == 0


# =============================================================================
# adw_config.py Tests
# =============================================================================

def test_load_settings_no_config():
    """Test that None is returned when no config files exist."""
    # Clear cache and mock non-existent paths
    adw_config.clear_settings_cache()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(adw_config, '_get_global_config_path', return_value=Path(tmpdir) / "global"):
            with patch.object(adw_config, '_get_local_config_path', return_value=Path(tmpdir) / "local"):
                result = adw_config.load_adw_settings(force_reload=True)
                return result is None


def test_load_settings_global_only():
    """Test loading settings from global config only."""
    adw_config.clear_settings_cache()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create global config
        global_dir = Path(tmpdir) / "global"
        global_dir.mkdir()
        global_config = global_dir / "settings.json"
        global_config.write_text(json.dumps({
            "logging_directory": "/var/log/adw",
            "verbosity": 2,
            "claude_mode": "apikey"
        }))

        with patch.object(adw_config, '_get_global_config_path', return_value=global_dir):
            with patch.object(adw_config, '_get_local_config_path', return_value=Path(tmpdir) / "local"):
                result = adw_config.load_adw_settings(force_reload=True)

                return (
                    result is not None and
                    result.get("logging_directory") == "/var/log/adw" and
                    result.get("verbosity") == 2 and
                    result.get("claude_mode") == "apikey"
                )


def test_load_settings_local_override():
    """Test that local settings override global settings."""
    adw_config.clear_settings_cache()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create global config
        global_dir = Path(tmpdir) / "global"
        global_dir.mkdir()
        (global_dir / "settings.json").write_text(json.dumps({
            "logging_directory": "/var/log/adw",
            "verbosity": 1,
            "claude_mode": "default"
        }))

        # Create local config (overrides some values)
        local_dir = Path(tmpdir) / "local"
        local_dir.mkdir()
        (local_dir / "settings.json").write_text(json.dumps({
            "logging_directory": "logs/adw",  # Override
            "verbosity": 2  # Override, claude_mode inherited
        }))

        with patch.object(adw_config, '_get_global_config_path', return_value=global_dir):
            with patch.object(adw_config, '_get_local_config_path', return_value=local_dir):
                result = adw_config.load_adw_settings(force_reload=True)

                return (
                    result is not None and
                    result.get("logging_directory") == "logs/adw" and  # Local override
                    result.get("verbosity") == 2 and  # Local override
                    result.get("claude_mode") == "default"  # Inherited from global
                )


def test_settings_caching():
    """Test that settings are cached after first load."""
    adw_config.clear_settings_cache()

    with tempfile.TemporaryDirectory() as tmpdir:
        global_dir = Path(tmpdir) / "global"
        global_dir.mkdir()
        config_file = global_dir / "settings.json"
        config_file.write_text(json.dumps({"verbosity": 1}))

        with patch.object(adw_config, '_get_global_config_path', return_value=global_dir):
            with patch.object(adw_config, '_get_local_config_path', return_value=Path(tmpdir) / "local"):
                # First load
                result1 = adw_config.load_adw_settings(force_reload=True)

                # Modify file
                config_file.write_text(json.dumps({"verbosity": 2}))

                # Second load (should be cached)
                result2 = adw_config.load_adw_settings()

                # Force reload to get new value
                result3 = adw_config.load_adw_settings(force_reload=True)

                return (
                    result1.get("verbosity") == 1 and
                    result2.get("verbosity") == 1 and  # Still cached
                    result3.get("verbosity") == 2  # Reloaded
                )


def test_resolve_path_absolute():
    """Test that absolute paths are returned as-is."""
    if sys.platform == "win32":
        # Windows absolute path
        result = adw_config._resolve_path("C:\\var\\log\\adw")
        return result == "C:\\var\\log\\adw"
    else:
        # Unix absolute path
        result = adw_config._resolve_path("/var/log/adw")
        return result == "/var/log/adw"


def test_resolve_path_tilde():
    """Test that tilde paths are expanded."""
    result = adw_config._resolve_path("~/logs/adw")
    expected = str(Path.home() / "logs" / "adw")
    return result == expected


def test_resolve_path_relative():
    """Test that relative paths are resolved from base directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = adw_config._resolve_path("logs/adw", Path(tmpdir))
        expected = str(Path(tmpdir) / "logs" / "adw")
        return result == expected


def test_get_verbosity_default():
    """Test default verbosity when no config."""
    adw_config.clear_settings_cache()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(adw_config, '_get_global_config_path', return_value=Path(tmpdir) / "global"):
            with patch.object(adw_config, '_get_local_config_path', return_value=Path(tmpdir) / "local"):
                result = adw_config.get_verbosity()
                return result == 1  # Default


def test_get_verbosity_clamped():
    """Test that verbosity is clamped to valid range."""
    adw_config.clear_settings_cache()

    with tempfile.TemporaryDirectory() as tmpdir:
        global_dir = Path(tmpdir) / "global"
        global_dir.mkdir()
        (global_dir / "settings.json").write_text(json.dumps({"verbosity": 99}))

        with patch.object(adw_config, '_get_global_config_path', return_value=global_dir):
            with patch.object(adw_config, '_get_local_config_path', return_value=Path(tmpdir) / "local"):
                adw_config.load_adw_settings(force_reload=True)
                result = adw_config.get_verbosity()
                return result == 2  # Clamped to max


def test_get_claude_mode_default():
    """Test default Claude mode."""
    adw_config.clear_settings_cache()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(adw_config, '_get_global_config_path', return_value=Path(tmpdir) / "global"):
            with patch.object(adw_config, '_get_local_config_path', return_value=Path(tmpdir) / "local"):
                result = adw_config.get_claude_mode()
                return result == "default"


def test_detect_claude_mode_apikey():
    """Test Claude mode detection with API key."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test123"}):
        result = adw_config.detect_claude_mode()
        return result == "apikey"


def test_detect_claude_mode_unknown():
    """Test Claude mode detection when no credentials."""
    # Remove API key and mock no credentials file
    env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

    with patch.dict(os.environ, env_without_key, clear=True):
        with patch.object(Path, 'exists', return_value=False):
            result = adw_config.detect_claude_mode()
            return result == "unknown"


# =============================================================================
# execution_log.py Tests
# =============================================================================

def test_iso_timestamp_format():
    """Test that ISO timestamp is in correct format."""
    ts = _get_iso_timestamp()
    # Should be ISO 8601 with timezone
    return (
        "T" in ts and
        ("+" in ts or "Z" in ts) and
        len(ts) >= 20
    )


def test_sanitize_env_vars_masks_secrets():
    """Test that sensitive environment variables are masked."""
    with patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "sk-ant-1234567890abcdef",
        "GITHUB_PAT": "ghp_abcdefghijklmnop",
        "GITHUB_REPO_URL": "https://github.com/user/repo"
    }):
        result = _sanitize_env_vars()

        return (
            "***" in result.get("ANTHROPIC_API_KEY", "") and
            "***" in result.get("GITHUB_PAT", "") and
            "https://github.com" in result.get("GITHUB_REPO_URL", "")  # Not masked
        )


def test_subprocess_tracking():
    """Test subprocess start/end tracking."""
    import time

    invocation = track_subprocess_start("adw_plan_iso.py")

    # Check initial state
    initial_ok = (
        invocation.script_name == "adw_plan_iso.py" and
        invocation.invocation_time is not None and
        invocation.end_time is None
    )

    # Simulate some work
    time.sleep(0.1)

    # Complete tracking
    completed = track_subprocess_end(invocation, 0)

    # Check completed state
    completed_ok = (
        completed.end_time is not None and
        completed.return_code == 0 and
        completed.success is True and
        completed.duration_seconds >= 0.1
    )

    return initial_ok and completed_ok


def test_subprocess_tracking_failure():
    """Test subprocess tracking with non-zero return code."""
    invocation = track_subprocess_start("adw_build_iso.py")
    completed = track_subprocess_end(invocation, 1)

    return (
        completed.return_code == 1 and
        completed.success is False
    )


def test_agent_metrics_tracking():
    """Test agent execution metrics tracking."""
    _reset_agent_metrics()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock output file
        output_file = os.path.join(tmpdir, "raw_output.jsonl")
        with open(output_file, "w") as f:
            f.write('{"type": "message", "text": "Hello"}\n')
            f.write('{"type": "result", "total_cost_usd": 0.05, "duration_api_ms": 1000}\n')

        # Enable logging for this test
        with patch('adw_modules.execution_log.is_logging_enabled', return_value=True):
            track_agent_execution("test1234", output_file)

        metrics = _get_agent_metrics()

        return (
            metrics.total_cost_usd == 0.05 and
            metrics.total_api_duration_ms == 1000 and
            metrics.num_agent_calls == 1
        )


def test_agent_metrics_aggregation():
    """Test that multiple agent executions are aggregated."""
    _reset_agent_metrics()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple output files
        for i, cost in enumerate([0.05, 0.10, 0.03]):
            output_file = os.path.join(tmpdir, f"output_{i}.jsonl")
            with open(output_file, "w") as f:
                f.write(f'{{"type": "result", "total_cost_usd": {cost}, "duration_api_ms": 1000}}\n')

            with patch('adw_modules.execution_log.is_logging_enabled', return_value=True):
                track_agent_execution("test1234", output_file)

        metrics = _get_agent_metrics()

        return (
            abs(metrics.total_cost_usd - 0.18) < 0.001 and
            metrics.total_api_duration_ms == 3000 and
            metrics.num_agent_calls == 3
        )


def test_file_info_basic():
    """Test basic file info retrieval."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = os.path.join(tmpdir, "test.txt")
        with open(test_file, "w") as f:
            f.write("Hello, World!")

        info = get_file_info("test.txt", tmpdir)

        return (
            info.path == "test.txt" and
            info.size_bytes == 13
        )


def test_files_summary_model():
    """Test FilesSummary model creation."""
    summary = FilesSummary(
        created_count=3,
        modified_count=2,
        deleted_count=1
    )

    return (
        summary.created_count == 3 and
        summary.modified_count == 2 and
        summary.deleted_count == 1
    )


def test_start_log_entry_creation():
    """Test StartLogEntry model creation."""
    entry = StartLogEntry(
        timestamp=_get_iso_timestamp(),
        message="Starting test workflow",
        script_name="test_script.py",
        adw_id="test1234",
        project_directory="/home/user/project",
        command_args=["test_script.py", "123"],
        environment={"TEST": "value"},
        python_version="3.13.0",
        platform="linux"
    )

    return (
        entry.event_type == "start" and
        entry.level == "info" and
        entry.script_name == "test_script.py" and
        entry.adw_id == "test1234"
    )


def test_end_log_entry_success():
    """Test EndLogEntry model for successful execution."""
    entry = EndLogEntry(
        timestamp=_get_iso_timestamp(),
        message="Workflow completed successfully",
        script_name="test_script.py",
        adw_id="test1234",
        project_directory="/home/user/project",
        execution_time_seconds=123.45,
        exit_code=0,
        success=True,
        num_agent_calls=5,
        claude_mode="apikey"
    )

    return (
        entry.event_type == "end" and
        entry.level == "info" and
        entry.success is True and
        entry.exit_code == 0
    )


def test_end_log_entry_failure():
    """Test EndLogEntry model for failed execution."""
    entry = EndLogEntry(
        timestamp=_get_iso_timestamp(),
        level="error",
        message="Workflow failed",
        script_name="test_script.py",
        adw_id="test1234",
        project_directory="/home/user/project",
        execution_time_seconds=45.2,
        exit_code=1,
        success=False,
        error_type="RuntimeError",
        error_message="Build failed",
        num_agent_calls=2,
        claude_mode="unknown"
    )

    return (
        entry.level == "error" and
        entry.success is False and
        entry.exit_code == 1 and
        entry.error_type == "RuntimeError"
    )


def test_log_execution_start_disabled():
    """Test that log_execution_start returns None when logging disabled."""
    with patch('adw_modules.execution_log.is_logging_enabled', return_value=False):
        result = log_execution_start(
            script_name="test.py",
            adw_id="test1234"
        )
        return result is None


def test_log_execution_end_disabled():
    """Test that log_execution_end returns None when logging disabled."""
    with patch('adw_modules.execution_log.is_logging_enabled', return_value=False):
        result = log_execution_end(start_entry=None)
        return result is None


def test_log_execution_full_cycle():
    """Test full logging cycle with start and end."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "adw_execution.log.jsonl")

        # Mock config to enable logging
        with patch('adw_modules.execution_log.is_logging_enabled', return_value=True):
            with patch('adw_modules.execution_log.get_log_file_path', return_value=log_file):
                with patch('adw_modules.execution_log.ensure_logging_directory', return_value=tmpdir):
                    with patch('adw_modules.execution_log.get_verbosity', return_value=1):
                        with patch('adw_modules.execution_log.detect_claude_mode', return_value="apikey"):
                            # Reset metrics
                            _reset_agent_metrics()

                            # Log start
                            start_entry = log_execution_start(
                                script_name="test_script.py",
                                adw_id="test1234",
                                issue_number="123"
                            )

                            # Log end
                            end_entry = log_execution_end(
                                start_entry=start_entry,
                                exit_code=0,
                                success=True
                            )

        # Read log file
        if not os.path.exists(log_file):
            return False

        with open(log_file, "r") as f:
            lines = f.readlines()

        if len(lines) != 2:
            return False

        start_data = json.loads(lines[0])
        end_data = json.loads(lines[1])

        return (
            start_data.get("event_type") == "start" and
            start_data.get("script_name") == "test_script.py" and
            end_data.get("event_type") == "end" and
            end_data.get("success") is True
        )


def test_verbosity_level_0():
    """Test file tracking at verbosity level 0 (summary only)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "adw_execution.log.jsonl")

        with patch('adw_modules.execution_log.is_logging_enabled', return_value=True):
            with patch('adw_modules.execution_log.get_log_file_path', return_value=log_file):
                with patch('adw_modules.execution_log.ensure_logging_directory', return_value=tmpdir):
                    with patch('adw_modules.execution_log.get_verbosity', return_value=0):
                        with patch('adw_modules.execution_log.detect_claude_mode', return_value="apikey"):
                            with patch('adw_modules.execution_log.get_files_changed_since', return_value=(["a.py", "b.py"], ["c.py"], [])):
                                _reset_agent_metrics()

                                start_entry = log_execution_start(
                                    script_name="test.py",
                                    adw_id="test1234"
                                )

                                # Mock start commit
                                start_entry._start_commit = "abc123"

                                end_entry = log_execution_end(
                                    start_entry=start_entry,
                                    exit_code=0,
                                    success=True
                                )

        with open(log_file, "r") as f:
            lines = f.readlines()

        end_data = json.loads(lines[1])

        # Verbosity 0 should have files_summary, not individual file lists
        return (
            end_data.get("files_summary") is not None and
            end_data.get("files_summary", {}).get("created_count") == 2 and
            end_data.get("files_summary", {}).get("modified_count") == 1 and
            end_data.get("files_created") is None
        )


def test_verbosity_level_1():
    """Test file tracking at verbosity level 1 (file names)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "adw_execution.log.jsonl")

        with patch('adw_modules.execution_log.is_logging_enabled', return_value=True):
            with patch('adw_modules.execution_log.get_log_file_path', return_value=log_file):
                with patch('adw_modules.execution_log.ensure_logging_directory', return_value=tmpdir):
                    with patch('adw_modules.execution_log.get_verbosity', return_value=1):
                        with patch('adw_modules.execution_log.detect_claude_mode', return_value="apikey"):
                            with patch('adw_modules.execution_log.get_files_changed_since', return_value=(["a.py", "b.py"], ["c.py"], [])):
                                _reset_agent_metrics()

                                start_entry = log_execution_start(
                                    script_name="test.py",
                                    adw_id="test1234"
                                )
                                start_entry._start_commit = "abc123"

                                end_entry = log_execution_end(
                                    start_entry=start_entry,
                                    exit_code=0,
                                    success=True
                                )

        with open(log_file, "r") as f:
            lines = f.readlines()

        end_data = json.loads(lines[1])

        # Verbosity 1 should have file lists as strings
        return (
            end_data.get("files_summary") is None and
            end_data.get("files_created") == ["a.py", "b.py"] and
            end_data.get("files_modified") == ["c.py"]
        )


def test_subprocess_list_in_end_entry():
    """Test that subprocess list is included in end entry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "adw_execution.log.jsonl")

        with patch('adw_modules.execution_log.is_logging_enabled', return_value=True):
            with patch('adw_modules.execution_log.get_log_file_path', return_value=log_file):
                with patch('adw_modules.execution_log.ensure_logging_directory', return_value=tmpdir):
                    with patch('adw_modules.execution_log.get_verbosity', return_value=1):
                        with patch('adw_modules.execution_log.detect_claude_mode', return_value="apikey"):
                            _reset_agent_metrics()

                            start_entry = log_execution_start(
                                script_name="adw_sdlc_iso.py",
                                adw_id="test1234"
                            )

                            # Create subprocess invocations
                            subprocesses = []

                            inv1 = track_subprocess_start("adw_plan_iso.py")
                            inv1 = track_subprocess_end(inv1, 0)
                            subprocesses.append(inv1)

                            inv2 = track_subprocess_start("adw_build_iso.py")
                            inv2 = track_subprocess_end(inv2, 1)  # Failed
                            subprocesses.append(inv2)

                            end_entry = log_execution_end(
                                start_entry=start_entry,
                                exit_code=0,
                                success=True,
                                subprocesses=subprocesses
                            )

        with open(log_file, "r") as f:
            lines = f.readlines()

        end_data = json.loads(lines[1])

        return (
            end_data.get("subprocess_count") == 2 and
            end_data.get("subprocess_failures") == 1 and
            len(end_data.get("subprocesses", [])) == 2
        )


def test_error_info_in_end_entry():
    """Test that error info is included in end entry on failure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = os.path.join(tmpdir, "adw_execution.log.jsonl")

        with patch('adw_modules.execution_log.is_logging_enabled', return_value=True):
            with patch('adw_modules.execution_log.get_log_file_path', return_value=log_file):
                with patch('adw_modules.execution_log.ensure_logging_directory', return_value=tmpdir):
                    with patch('adw_modules.execution_log.get_verbosity', return_value=1):
                        with patch('adw_modules.execution_log.detect_claude_mode', return_value="apikey"):
                            _reset_agent_metrics()

                            start_entry = log_execution_start(
                                script_name="test.py",
                                adw_id="test1234"
                            )

                            end_entry = log_execution_end(
                                start_entry=start_entry,
                                exit_code=1,
                                success=False,
                                error_type="RuntimeError",
                                error_message="Something went wrong"
                            )

        with open(log_file, "r") as f:
            lines = f.readlines()

        end_data = json.loads(lines[1])

        return (
            end_data.get("level") == "error" and
            end_data.get("success") is False and
            end_data.get("error_type") == "RuntimeError" and
            "Something went wrong" in end_data.get("error_message", "")
        )


# =============================================================================
# Main
# =============================================================================

def main():
    """Run all tests."""
    print("ADW Execution Logging Tests")
    print("=" * 50)

    runner = TestRunner()

    # adw_config.py tests
    print("\nadw_config.py tests:")
    runner.run_test("load_settings_no_config", test_load_settings_no_config)
    runner.run_test("load_settings_global_only", test_load_settings_global_only)
    runner.run_test("load_settings_local_override", test_load_settings_local_override)
    runner.run_test("settings_caching", test_settings_caching)
    runner.run_test("resolve_path_absolute", test_resolve_path_absolute)
    runner.run_test("resolve_path_tilde", test_resolve_path_tilde)
    runner.run_test("resolve_path_relative", test_resolve_path_relative)
    runner.run_test("get_verbosity_default", test_get_verbosity_default)
    runner.run_test("get_verbosity_clamped", test_get_verbosity_clamped)
    runner.run_test("get_claude_mode_default", test_get_claude_mode_default)
    runner.run_test("detect_claude_mode_apikey", test_detect_claude_mode_apikey)
    runner.run_test("detect_claude_mode_unknown", test_detect_claude_mode_unknown)

    # execution_log.py tests
    print("\nexecution_log.py tests:")
    runner.run_test("iso_timestamp_format", test_iso_timestamp_format)
    runner.run_test("sanitize_env_vars_masks_secrets", test_sanitize_env_vars_masks_secrets)
    runner.run_test("subprocess_tracking", test_subprocess_tracking)
    runner.run_test("subprocess_tracking_failure", test_subprocess_tracking_failure)
    runner.run_test("agent_metrics_tracking", test_agent_metrics_tracking)
    runner.run_test("agent_metrics_aggregation", test_agent_metrics_aggregation)
    runner.run_test("file_info_basic", test_file_info_basic)
    runner.run_test("files_summary_model", test_files_summary_model)
    runner.run_test("start_log_entry_creation", test_start_log_entry_creation)
    runner.run_test("end_log_entry_success", test_end_log_entry_success)
    runner.run_test("end_log_entry_failure", test_end_log_entry_failure)
    runner.run_test("log_execution_start_disabled", test_log_execution_start_disabled)
    runner.run_test("log_execution_end_disabled", test_log_execution_end_disabled)
    runner.run_test("log_execution_full_cycle", test_log_execution_full_cycle)
    runner.run_test("verbosity_level_0", test_verbosity_level_0)
    runner.run_test("verbosity_level_1", test_verbosity_level_1)
    runner.run_test("subprocess_list_in_end_entry", test_subprocess_list_in_end_entry)
    runner.run_test("error_info_in_end_entry", test_error_info_in_end_entry)

    success = runner.summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
