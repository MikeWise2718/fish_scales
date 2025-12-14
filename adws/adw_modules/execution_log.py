"""Execution logging for ADW workflows.

Provides comprehensive JSONL execution logging for ADW workflow scripts.
Each workflow execution generates start and end log entries containing
execution metadata, performance metrics, token consumption, and file
modification tracking.
"""

import json
import os
import platform
import subprocess
import sys
import time
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Union, Tuple

from pydantic import BaseModel, Field

from .adw_config import (
    get_log_file_path,
    get_verbosity,
    detect_claude_mode,
    ensure_logging_directory,
    is_logging_enabled,
)


# Thread-local storage for tracking agent executions
_agent_tracking = threading.local()


# =============================================================================
# Data Types
# =============================================================================


class FileInfo(BaseModel):
    """Detailed file information for verbosity level 2."""

    path: str
    size_bytes: int
    lines_added: Optional[int] = None  # For modified files only
    lines_removed: Optional[int] = None  # For modified files only


class FilesSummary(BaseModel):
    """Summary counts for verbosity level 0."""

    created_count: int
    modified_count: int
    deleted_count: int


class SubprocessInvocation(BaseModel):
    """Tracks a subprocess invocation by an orchestrator script."""

    script_name: str
    invocation_time: str  # ISO 8601
    end_time: Optional[str] = None  # ISO 8601
    duration_seconds: Optional[float] = None
    return_code: Optional[int] = None
    success: Optional[bool] = None


class AgentMetrics(BaseModel):
    """Aggregated metrics from Claude Code agent executions."""

    total_cost_usd: float = 0.0
    total_api_duration_ms: int = 0
    num_agent_calls: int = 0
    models_used: List[str] = Field(default_factory=list)
    total_tokens_input: Optional[int] = None
    total_tokens_output: Optional[int] = None


class StartLogEntry(BaseModel):
    """Log entry at script startup."""

    timestamp: str  # ISO 8601 format
    event_type: Literal["start"] = "start"
    level: Literal["info"] = "info"
    message: str
    script_name: str  # e.g., "adw_plan_iso.py"
    adw_id: str  # 8-char workflow ID
    project_directory: str  # Absolute path to project root
    worktree_path: Optional[str] = None  # Path to worktree if applicable
    issue_number: Optional[str] = None
    command_args: List[str]  # sys.argv
    environment: Dict[str, str]  # Relevant env vars (sanitized)
    git_branch: Optional[str] = None
    git_commit_hash: Optional[str] = None  # HEAD at start
    python_version: str
    platform: str  # e.g., "win32", "darwin", "linux"


class EndLogEntry(BaseModel):
    """Log entry at script completion."""

    timestamp: str  # ISO 8601 format
    event_type: Literal["end"] = "end"
    level: Literal["info", "warning", "error"] = "info"
    message: str
    script_name: str
    adw_id: str
    project_directory: str
    worktree_path: Optional[str] = None
    issue_number: Optional[str] = None
    execution_time_seconds: float
    exit_code: int
    success: bool

    # File tracking (format depends on verbosity setting)
    files_summary: Optional[FilesSummary] = None  # Verbosity 0
    files_created: Optional[Union[List[str], List[FileInfo]]] = None  # Verbosity 1-2
    files_modified: Optional[Union[List[str], List[FileInfo]]] = None  # Verbosity 1-2
    files_deleted: Optional[Union[List[str], List[FileInfo]]] = None  # Verbosity 1-2

    # Token/cost consumption (aggregated from all agent calls)
    total_tokens_input: Optional[int] = None
    total_tokens_output: Optional[int] = None
    total_cost_usd: Optional[float] = None
    total_api_duration_ms: Optional[int] = None
    num_agent_calls: int = 0

    # Licensing info
    claude_mode: Literal["apikey", "max", "unknown"] = "unknown"
    model_set_used: Optional[str] = None  # "base" or "heavy"
    models_used: List[str] = Field(default_factory=list)

    # Subprocess tracking (for orchestrator scripts only)
    subprocesses: List[SubprocessInvocation] = Field(default_factory=list)
    subprocess_count: int = 0
    subprocess_failures: int = 0

    # Error info (if failed)
    error_type: Optional[str] = None
    error_message: Optional[str] = None


# =============================================================================
# Helper Functions
# =============================================================================


def _get_iso_timestamp() -> str:
    """Get current timestamp in ISO 8601 format with timezone."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _sanitize_env_vars() -> Dict[str, str]:
    """Get relevant environment variables with sensitive values masked."""
    relevant_vars = [
        "ANTHROPIC_API_KEY",
        "GITHUB_PAT",
        "GITHUB_REPO_URL",
        "CLAUDE_CODE_PATH",
        "ADW_DEBUG",
    ]

    result = {}
    for var in relevant_vars:
        value = os.environ.get(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "PAT" in var or "TOKEN" in var or "SECRET" in var:
                result[var] = f"{value[:8]}***" if len(value) > 8 else "***"
            else:
                result[var] = value

    return result


def _get_git_branch(cwd: Optional[str] = None) -> Optional[str]:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_git_commit_hash(cwd: Optional[str] = None) -> Optional[str]:
    """Get current git HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _get_project_directory() -> str:
    """Get the project root directory."""
    # __file__ is in adws/adw_modules/, so go up 3 levels
    return os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


def _write_log_entry(entry: Union[StartLogEntry, EndLogEntry]) -> bool:
    """Write a log entry to the JSONL log file.

    Args:
        entry: The log entry to write

    Returns:
        True if successful, False otherwise
    """
    log_file = get_log_file_path()
    if not log_file:
        return False

    try:
        # Ensure directory exists
        ensure_logging_directory()

        # Append to log file
        with open(log_file, "a", encoding="utf-8") as f:
            # Use exclude_none to avoid writing null values
            json_str = entry.model_dump_json(exclude_none=True)
            f.write(json_str + "\n")

        return True
    except Exception as e:
        # Log errors silently - don't interrupt workflow
        print(f"WARNING: Failed to write execution log: {e}", file=sys.stderr)
        return False


# =============================================================================
# File Change Tracking
# =============================================================================


def get_files_changed_since(
    start_commit: str, cwd: Optional[str] = None
) -> Tuple[List[str], List[str], List[str]]:
    """Get files created, modified, deleted since start_commit.

    Args:
        start_commit: Git commit hash to compare against
        cwd: Working directory (worktree_path for iso workflows)

    Returns:
        Tuple of (created, modified, deleted) file lists
    """
    created = []
    modified = []
    deleted = []

    try:
        # Get diff between start_commit and current state
        result = subprocess.run(
            ["git", "diff", "--name-status", start_commit],
            capture_output=True,
            text=True,
            cwd=cwd,
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t", 1)
                if len(parts) != 2:
                    continue

                status, path = parts
                if status.startswith("A"):
                    created.append(path)
                elif status.startswith("M"):
                    modified.append(path)
                elif status.startswith("D"):
                    deleted.append(path)
                elif status.startswith("R"):
                    # Rename: old -> new
                    modified.append(path)

        # Also check for untracked files
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                status = line[:2]
                path = line[3:]

                if status == "??":
                    # Untracked file
                    if path not in created:
                        created.append(path)
                elif status[0] == "A" or status[1] == "A":
                    if path not in created:
                        created.append(path)
                elif status[0] == "M" or status[1] == "M":
                    if path not in modified:
                        modified.append(path)
                elif status[0] == "D" or status[1] == "D":
                    if path not in deleted:
                        deleted.append(path)

    except Exception:
        pass

    return created, modified, deleted


def get_file_info(path: str, cwd: Optional[str] = None) -> FileInfo:
    """Get detailed information about a file.

    Args:
        path: Relative path to file
        cwd: Working directory

    Returns:
        FileInfo with size and optionally diff stats
    """
    full_path = os.path.join(cwd or ".", path)

    size_bytes = 0
    if os.path.exists(full_path):
        try:
            size_bytes = os.path.getsize(full_path)
        except OSError:
            pass

    return FileInfo(path=path, size_bytes=size_bytes)


def get_file_info_with_diff(
    path: str, start_commit: str, cwd: Optional[str] = None
) -> FileInfo:
    """Get detailed file information including diff statistics.

    Args:
        path: Relative path to file
        start_commit: Git commit to compare against
        cwd: Working directory

    Returns:
        FileInfo with size and diff stats
    """
    info = get_file_info(path, cwd)

    try:
        result = subprocess.run(
            ["git", "diff", "--numstat", start_commit, "--", path],
            capture_output=True,
            text=True,
            cwd=cwd,
        )

        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split("\t")
            if len(parts) >= 2:
                try:
                    info.lines_added = int(parts[0]) if parts[0] != "-" else None
                    info.lines_removed = int(parts[1]) if parts[1] != "-" else None
                except ValueError:
                    pass
    except Exception:
        pass

    return info


# =============================================================================
# Agent Execution Tracking
# =============================================================================


def _get_agent_metrics() -> AgentMetrics:
    """Get the current agent metrics from thread-local storage."""
    if not hasattr(_agent_tracking, "metrics"):
        _agent_tracking.metrics = AgentMetrics()
    return _agent_tracking.metrics


def _reset_agent_metrics() -> None:
    """Reset agent metrics for a new execution."""
    _agent_tracking.metrics = AgentMetrics()


def track_agent_execution(adw_id: str, output_file: str) -> None:
    """Track an agent execution for later aggregation in end log.

    This should be called after each successful agent execution to
    accumulate metrics for the end log entry.

    Args:
        adw_id: The ADW ID for the workflow
        output_file: Path to the raw_output.jsonl file
    """
    if not is_logging_enabled():
        return

    metrics = _get_agent_metrics()

    try:
        # Parse the output file to extract metrics
        if os.path.exists(output_file):
            with open(output_file, "r") as f:
                # Read all lines and find the result message (last line)
                lines = f.readlines()
                for line in reversed(lines):
                    try:
                        data = json.loads(line)
                        if data.get("type") == "result":
                            # Extract metrics
                            metrics.total_cost_usd += data.get("total_cost_usd", 0.0)
                            metrics.total_api_duration_ms += data.get(
                                "duration_api_ms", 0
                            )
                            metrics.num_agent_calls += 1

                            # Extract token counts if available
                            if data.get("input_tokens"):
                                if metrics.total_tokens_input is None:
                                    metrics.total_tokens_input = 0
                                metrics.total_tokens_input += data.get("input_tokens", 0)

                            if data.get("output_tokens"):
                                if metrics.total_tokens_output is None:
                                    metrics.total_tokens_output = 0
                                metrics.total_tokens_output += data.get("output_tokens", 0)

                            break
                    except json.JSONDecodeError:
                        continue

    except Exception:
        pass


# =============================================================================
# Subprocess Tracking (for orchestrator scripts)
# =============================================================================


def track_subprocess_start(script_name: str) -> SubprocessInvocation:
    """Record start of a subprocess invocation.

    Args:
        script_name: Name of the script being invoked

    Returns:
        Partial SubprocessInvocation to be completed later
    """
    return SubprocessInvocation(
        script_name=script_name,
        invocation_time=_get_iso_timestamp(),
    )


def track_subprocess_end(
    invocation: SubprocessInvocation, return_code: int
) -> SubprocessInvocation:
    """Complete subprocess tracking with end time and return code.

    Args:
        invocation: The partial invocation from track_subprocess_start
        return_code: Process exit code

    Returns:
        Completed SubprocessInvocation
    """
    end_time = _get_iso_timestamp()

    # Calculate duration
    try:
        start_dt = datetime.fromisoformat(invocation.invocation_time)
        end_dt = datetime.fromisoformat(end_time)
        duration = (end_dt - start_dt).total_seconds()
    except Exception:
        duration = 0.0

    invocation.end_time = end_time
    invocation.duration_seconds = duration
    invocation.return_code = return_code
    invocation.success = return_code == 0

    return invocation


# =============================================================================
# Main Logging Functions
# =============================================================================


def log_execution_start(
    script_name: str,
    adw_id: str,
    issue_number: Optional[str] = None,
    worktree_path: Optional[str] = None,
) -> Optional[StartLogEntry]:
    """Log script startup.

    Args:
        script_name: Name of the script (e.g., "adw_plan_iso.py")
        adw_id: 8-character workflow ID
        issue_number: GitHub issue number if applicable
        worktree_path: Path to worktree if applicable

    Returns:
        StartLogEntry for later reference, or None if logging disabled
    """
    if not is_logging_enabled():
        return None

    # Reset agent metrics for this execution
    _reset_agent_metrics()

    project_dir = _get_project_directory()
    cwd = worktree_path or project_dir

    entry = StartLogEntry(
        timestamp=_get_iso_timestamp(),
        message=f"Starting {script_name} workflow"
        + (f" for issue #{issue_number}" if issue_number else ""),
        script_name=script_name,
        adw_id=adw_id,
        project_directory=project_dir,
        worktree_path=worktree_path,
        issue_number=issue_number,
        command_args=sys.argv,
        environment=_sanitize_env_vars(),
        git_branch=_get_git_branch(cwd),
        git_commit_hash=_get_git_commit_hash(cwd),
        python_version=platform.python_version(),
        platform=sys.platform,
    )

    _write_log_entry(entry)

    # Store start time and commit hash for later use
    entry._start_time = time.time()  # type: ignore
    entry._start_commit = entry.git_commit_hash  # type: ignore

    return entry


def log_execution_end(
    start_entry: Optional[StartLogEntry],
    exit_code: int = 0,
    success: bool = True,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    subprocesses: Optional[List[SubprocessInvocation]] = None,
    model_set: Optional[str] = None,
) -> Optional[EndLogEntry]:
    """Log script completion with aggregated metrics.

    Args:
        start_entry: The StartLogEntry from log_execution_start
        exit_code: Process exit code
        success: Whether the script succeeded
        error_type: Exception type name if failed
        error_message: Error message if failed
        subprocesses: List of subprocess invocations (for orchestrators)
        model_set: Model set used ("base" or "heavy")

    Returns:
        EndLogEntry, or None if logging disabled
    """
    if not is_logging_enabled() or start_entry is None:
        return None

    # Calculate execution time
    start_time = getattr(start_entry, "_start_time", time.time())
    execution_time = time.time() - start_time

    # Get file changes
    start_commit = getattr(start_entry, "_start_commit", None)
    cwd = start_entry.worktree_path or start_entry.project_directory

    created, modified, deleted = [], [], []
    if start_commit:
        created, modified, deleted = get_files_changed_since(start_commit, cwd)

    # Get agent metrics
    metrics = _get_agent_metrics()

    # Determine log level
    level: Literal["info", "warning", "error"] = "info"
    if not success:
        level = "error" if exit_code != 0 else "warning"

    # Build message
    if success:
        cost_str = f"${metrics.total_cost_usd:.2f}" if metrics.total_cost_usd else ""
        message = f"Workflow completed successfully in {execution_time:.1f}s"
        if cost_str:
            message += f" ({cost_str})"
    else:
        message = f"Workflow failed: {error_type or 'Unknown'}"
        if error_message:
            message += f" - {error_message[:100]}"

    # Get Claude mode
    claude_mode = detect_claude_mode()

    # Handle subprocesses
    subprocess_list = subprocesses or []
    subprocess_count = len(subprocess_list)
    subprocess_failures = sum(1 for s in subprocess_list if not s.success)

    # Build file tracking based on verbosity
    verbosity = get_verbosity()

    files_summary = None
    files_created = None
    files_modified = None
    files_deleted = None

    if verbosity == 0:
        files_summary = FilesSummary(
            created_count=len(created),
            modified_count=len(modified),
            deleted_count=len(deleted),
        )
    elif verbosity == 1:
        files_created = created if created else None
        files_modified = modified if modified else None
        files_deleted = deleted if deleted else None
    elif verbosity == 2:
        if created:
            files_created = [get_file_info(f, cwd) for f in created]
        if modified and start_commit:
            files_modified = [get_file_info_with_diff(f, start_commit, cwd) for f in modified]
        elif modified:
            files_modified = [get_file_info(f, cwd) for f in modified]
        if deleted:
            files_deleted = [FileInfo(path=f, size_bytes=0) for f in deleted]

    entry = EndLogEntry(
        timestamp=_get_iso_timestamp(),
        level=level,
        message=message,
        script_name=start_entry.script_name,
        adw_id=start_entry.adw_id,
        project_directory=start_entry.project_directory,
        worktree_path=start_entry.worktree_path,
        issue_number=start_entry.issue_number,
        execution_time_seconds=execution_time,
        exit_code=exit_code,
        success=success,
        files_summary=files_summary,
        files_created=files_created,
        files_modified=files_modified,
        files_deleted=files_deleted,
        total_tokens_input=metrics.total_tokens_input,
        total_tokens_output=metrics.total_tokens_output,
        total_cost_usd=metrics.total_cost_usd if metrics.total_cost_usd > 0 else None,
        total_api_duration_ms=metrics.total_api_duration_ms if metrics.total_api_duration_ms > 0 else None,
        num_agent_calls=metrics.num_agent_calls,
        claude_mode=claude_mode,
        model_set_used=model_set,
        models_used=metrics.models_used if metrics.models_used else [],
        subprocesses=subprocess_list if subprocess_list else [],
        subprocess_count=subprocess_count if subprocess_count > 0 else 0,
        subprocess_failures=subprocess_failures if subprocess_failures > 0 else 0,
        error_type=error_type,
        error_message=error_message,
    )

    _write_log_entry(entry)
    return entry


@contextmanager
def execution_log_context(
    script_name: str,
    adw_id: str,
    issue_number: Optional[str] = None,
    worktree_path: Optional[str] = None,
):
    """Context manager for automatic start/end logging.

    Usage:
        with execution_log_context("adw_plan_iso.py", adw_id, issue_number) as start_entry:
            # ... workflow logic ...

    Args:
        script_name: Name of the script
        adw_id: 8-character workflow ID
        issue_number: GitHub issue number if applicable
        worktree_path: Path to worktree if applicable

    Yields:
        StartLogEntry for reference (may be None if logging disabled)
    """
    start_entry = log_execution_start(
        script_name=script_name,
        adw_id=adw_id,
        issue_number=issue_number,
        worktree_path=worktree_path,
    )

    exit_code = 0
    success = True
    error_type = None
    error_message = None

    try:
        yield start_entry
    except Exception as e:
        exit_code = 1
        success = False
        error_type = type(e).__name__
        error_message = str(e)
        raise
    finally:
        log_execution_end(
            start_entry=start_entry,
            exit_code=exit_code,
            success=success,
            error_type=error_type,
            error_message=error_message,
        )
