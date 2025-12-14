#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "schedule",
#     "python-dotenv",
#     "pydantic",
#     "rich>=13.7.0",
#     "rich-argparse>=1.4.0",
#     "anthropic>=0.70.0",
# ]
# ///

"""
Cron-based ADW trigger system that monitors GitHub issues and automatically processes them.

This script polls GitHub every 30 seconds (configurable) to detect:
1. New issues without comments
2. Issues where the latest comment is 'adw' or contains workflow specification

Workflow Selection:
- Default: adw_plan_build_iso (plan + build)
- Custom: Specify workflow in issue body or comment
  Example: "workflow: adw_sdlc_iso" or "adw_plan_build_test_iso"
- Model Set: Specify "model_set: heavy" for complex tasks (default: base)

When a qualifying issue is found, it triggers the specified workflow automatically.

Configuration:
- Polling interval: --polling-interval/-p (default: 30 seconds, range: 10-600)
- Workflow timeout: --workflow-timeout/-t (default: 1800 seconds / 30 minutes, range: 60-3600)
"""

import argparse
import os
import queue
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Set, Optional, Tuple

import schedule
from dotenv import load_dotenv
from rich_argparse import RichHelpFormatter

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from adw_modules.utils import get_safe_subprocess_env, make_adw_id, validate_anthropic_api_key
from adw_modules.console import (
    print_info,
    print_success,
    print_warning,
    print_error,
    print_debug,
    print_status,
)

from adw_modules.github import (
    fetch_open_issues,
    fetch_issue_comments,
    fetch_issue,
    get_repo_url,
    extract_repo_path,
    ADW_BOT_IDENTIFIER,
)
from adw_modules.workflow_ops import extract_adw_info
from adw_modules.state import ADWState

# Load environment variables from current or parent directories
load_dotenv()

# Configuration constants for argument validation
MIN_POLLING_INTERVAL = 10
MAX_POLLING_INTERVAL = 600
DEFAULT_POLLING_INTERVAL = 30

MIN_WORKFLOW_TIMEOUT = 60
MAX_WORKFLOW_TIMEOUT = 3600
DEFAULT_WORKFLOW_TIMEOUT = 1800  # 30 minutes - enough for UI features and complex workflows

# Optional environment variables
GITHUB_PAT = os.getenv("GITHUB_PAT")

# Get repository URL from git remote
try:
    GITHUB_REPO_URL = get_repo_url()
    REPO_PATH = extract_repo_path(GITHUB_REPO_URL)
except ValueError as e:
    print_error(f"ERROR: {e}")
    sys.exit(1)

# Dependent workflows that require existing worktrees
# These cannot be triggered directly without an ADW ID
DEPENDENT_WORKFLOWS = [
    "adw_build_iso",
    "adw_test_iso",
    "adw_review_iso",
    "adw_document_iso",
    "adw_ship_iso",
]

# Default workflow when none is specified
DEFAULT_WORKFLOW = "adw_plan_build_iso"

# Track processed issues
processed_issues: Set[int] = set()
# Track issues with their last processed comment ID
issue_last_comment: Dict[int, Optional[int]] = {}

# Graceful shutdown flag
shutdown_requested = False

# Global workflow timeout (set by main, used by check_and_process_issues)
workflow_timeout_seconds = DEFAULT_WORKFLOW_TIMEOUT


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    print_info(f"\nINFO: Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


def should_process_issue(issue_number: int) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """Determine if an issue should be processed based on comments.

    Returns:
        Tuple of (should_process, workflow, adw_id, model_set)
    """
    comments = fetch_issue_comments(REPO_PATH, issue_number)
    issue_details = fetch_issue(str(issue_number), REPO_PATH)
    issue_body = issue_details.body if issue_details else ""

    # Check if issue/comments are from ADW bot (prevent loops)
    if ADW_BOT_IDENTIFIER in issue_body:
        return (False, None, None, None)

    # If no comments, it's a new issue - check for workflow in issue body
    if not comments:
        print_info(f"INFO: Issue #{issue_number} has no comments - checking for workflow")

        # Check if issue body contains workflow specification
        if "adw_" in issue_body.lower():
            temp_id = make_adw_id()
            extraction_result = extract_adw_info(issue_body, temp_id)
            if extraction_result.has_workflow:
                print_info(f"INFO: Issue #{issue_number} specifies workflow: {extraction_result.workflow_command}")
                return (True, extraction_result.workflow_command, extraction_result.adw_id, extraction_result.model_set)

        # No workflow specified, use default
        print_info(f"INFO: Issue #{issue_number} - using default workflow: {DEFAULT_WORKFLOW}")
        return (True, DEFAULT_WORKFLOW, None, None)

    # Get the latest comment
    latest_comment = comments[-1]
    comment_body = latest_comment.get("body", "")
    comment_id = latest_comment.get("id")

    # Check if comment is from ADW bot (prevent loops)
    if ADW_BOT_IDENTIFIER in comment_body:
        return (False, None, None, None)

    # Check if we've already processed this comment
    last_processed_comment = issue_last_comment.get(issue_number)
    if last_processed_comment == comment_id:
        # DEBUG level - not printing
        return (False, None, None, None)

    # Check if latest comment is exactly 'adw' or contains workflow
    comment_lower = comment_body.strip().lower()
    if comment_lower == "adw" or "adw_" in comment_lower:
        issue_last_comment[issue_number] = comment_id

        # Try to extract workflow from comment
        if "adw_" in comment_lower:
            temp_id = make_adw_id()
            extraction_result = extract_adw_info(comment_body, temp_id)
            if extraction_result.has_workflow:
                print_info(f"INFO: Issue #{issue_number} - comment specifies workflow: {extraction_result.workflow_command}")
                return (True, extraction_result.workflow_command, extraction_result.adw_id, extraction_result.model_set)

        # Just 'adw' or failed to extract - check issue body for workflow
        if "adw_" in issue_body.lower():
            temp_id = make_adw_id()
            extraction_result = extract_adw_info(issue_body, temp_id)
            if extraction_result.has_workflow:
                print_info(f"INFO: Issue #{issue_number} - using workflow from issue body: {extraction_result.workflow_command}")
                return (True, extraction_result.workflow_command, extraction_result.adw_id, extraction_result.model_set)

        # Use default workflow
        print_info(f"INFO: Issue #{issue_number} - latest comment is 'adw' - using default workflow: {DEFAULT_WORKFLOW}")
        return (True, DEFAULT_WORKFLOW, None, None)

    # DEBUG level - not printing
    return (False, None, None, None)


def read_stream_with_tracking(stream, output_queue, stream_name):
    """
    Read from a stream and put lines into a queue with size tracking.

    This runs in a separate thread to continuously drain the pipe buffer
    and prevent deadlocks.

    Args:
        stream: The stream to read from (stdout or stderr)
        output_queue: Queue to put lines into
        stream_name: Name of the stream ('stdout' or 'stderr')
    """
    try:
        byte_count = 0
        line_count = 0

        for line in stream:
            byte_count += len(line.encode('utf-8'))
            line_count += 1
            output_queue.put((stream_name, 'line', line))

        # Send final statistics
        output_queue.put((stream_name, 'stats', {'bytes': byte_count, 'lines': line_count}))

    except Exception as e:
        output_queue.put((stream_name, 'error', str(e)))
    finally:
        output_queue.put((stream_name, 'eof', None))


def trigger_adw_workflow(
    issue_number: int,
    workflow: str = DEFAULT_WORKFLOW,
    provided_adw_id: Optional[str] = None,
    model_set: Optional[str] = None,
    timeout: int = DEFAULT_WORKFLOW_TIMEOUT,
) -> Tuple[bool, float]:
    """Trigger an ADW workflow for a specific issue.

    Args:
        issue_number: GitHub issue number
        workflow: Workflow name (e.g., 'adw_plan_build_iso', 'adw_sdlc_iso')
        provided_adw_id: Optional ADW ID (required for dependent workflows)
        model_set: Optional model set ('base' or 'heavy')
        timeout: Workflow execution timeout in seconds (default: 1800)

    Returns:
        Tuple of (success: bool, execution_time: float)
        - success: True if workflow was successfully triggered, False otherwise
        - execution_time: Workflow execution time in seconds
    """
    try:
        # Validate dependent workflows
        if workflow in DEPENDENT_WORKFLOWS:
            if not provided_adw_id:
                print_error(f"ERROR: {workflow} is a dependent workflow that requires an existing ADW ID")
                print_error(f"ERROR: Cannot trigger {workflow} without ADW ID from previous workflow run")
                print_info(f"INFO: To run this workflow, provide ADW ID in issue body or comment")
                print_info(f"INFO: Example: '{workflow} adw-12345678'")
                return (False, 0.0)

        # Build script path
        adws_dir = Path(__file__).parent.parent
        script_path = adws_dir / f"{workflow}.py"

        print_info(f"INFO: Triggering ADW workflow '{workflow}' for issue #{issue_number}")
        print_debug(f"DEBUG: Script path: {script_path}")
        print_debug(f"DEBUG: Python executable: {sys.executable}")
        if provided_adw_id:
            print_debug(f"DEBUG: Using provided ADW ID: {provided_adw_id}")
        if model_set:
            print_debug(f"DEBUG: Model set: {model_set}")

        # Verify script exists
        if not script_path.exists():
            print_error(f"ERROR: Workflow script not found at {script_path}")
            print_error(f"ERROR: Available workflows: {', '.join(DEPENDENT_WORKFLOWS + ['adw_plan_iso', 'adw_patch_iso', 'adw_sdlc_iso', DEFAULT_WORKFLOW])}")
            return (False, 0.0)

        # Generate or use provided ADW ID
        adw_id = provided_adw_id or make_adw_id()

        # Create/update state with workflow info
        state = ADWState(adw_id)
        state.update(
            adw_id=adw_id,
            issue_number=str(issue_number),
            model_set=model_set or "base",
        )
        state.save("trigger_cron")
        print_debug(f"DEBUG: ADW ID: {adw_id}")

        # Build command
        cmd = [sys.executable, str(script_path), str(issue_number), adw_id]
        print_debug(f"DEBUG: Command: {' '.join(cmd)}")
        print_debug(f"DEBUG: Working directory: {script_path.parent}")
        print_debug(f"DEBUG: Initial timeout: {timeout}s ({timeout//60} minutes)")

        # Run the workflow script with dynamic timeout adjustment
        # Use Popen for more control over execution monitoring
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=script_path.parent,
            env=get_safe_subprocess_env(),
        )

        start_time = time.time()
        current_timeout = timeout
        check_interval = 5  # Check state file every 5 seconds
        last_check_time = start_time

        # Start threads to continuously read from stdout/stderr
        # This prevents pipe buffer deadlocks
        output_queue = queue.Queue()

        stdout_thread = threading.Thread(
            target=read_stream_with_tracking,
            args=(process.stdout, output_queue, 'stdout'),
            daemon=True,
            name='stdout-reader'
        )
        stderr_thread = threading.Thread(
            target=read_stream_with_tracking,
            args=(process.stderr, output_queue, 'stderr'),
            daemon=True,
            name='stderr-reader'
        )

        stdout_thread.start()
        stderr_thread.start()

        # Collect output and track statistics
        stdout_lines = []
        stderr_lines = []
        stdout_stats = None
        stderr_stats = None
        stdout_eof = False
        stderr_eof = False

        # Poll the process and check for timeout adjustments
        while True:
            # Drain the output queue
            try:
                while True:
                    stream_name, msg_type, data = output_queue.get_nowait()

                    if msg_type == 'line':
                        if stream_name == 'stdout':
                            stdout_lines.append(data)
                        else:
                            stderr_lines.append(data)

                    elif msg_type == 'stats':
                        if stream_name == 'stdout':
                            stdout_stats = data
                        else:
                            stderr_stats = data

                    elif msg_type == 'eof':
                        if stream_name == 'stdout':
                            stdout_eof = True
                        else:
                            stderr_eof = True

                    elif msg_type == 'error':
                        print_debug(f"DEBUG: Error reading {stream_name}: {data}")

            except queue.Empty:
                pass

            # Check if process is still running
            returncode = process.poll()
            if returncode is not None:
                # Process completed - drain any remaining output
                time.sleep(0.1)  # Give threads time to finish
                try:
                    while True:
                        stream_name, msg_type, data = output_queue.get_nowait()
                        if msg_type == 'line':
                            if stream_name == 'stdout':
                                stdout_lines.append(data)
                            else:
                                stderr_lines.append(data)
                        elif msg_type == 'stats':
                            if stream_name == 'stdout':
                                stdout_stats = data
                            else:
                                stderr_stats = data
                except queue.Empty:
                    pass
                break

            elapsed = time.time() - start_time

            # Periodically check state file for complexity recommendation
            if time.time() - last_check_time >= check_interval:
                last_check_time = time.time()

                # Try to load state and check for recommended_timeout
                try:
                    loaded_state = ADWState.load(adw_id)
                    if loaded_state:
                        recommended = loaded_state.get("recommended_timeout")
                        if recommended and recommended > current_timeout:
                            old_timeout = current_timeout
                            current_timeout = recommended
                            print_info(f"INFO: ⏱️  Timeout adjusted based on complexity estimation:")
                            print_info(f"INFO:    Old timeout: {old_timeout}s ({old_timeout//60} min)")
                            print_info(f"INFO:    New timeout: {current_timeout}s ({current_timeout//60} min)")
                            print_info(f"INFO:    Complexity: {loaded_state.get('complexity', 'unknown')}")
                except Exception as e:
                    # Ignore errors reading state - don't interrupt workflow
                    print_debug(f"DEBUG: Could not check state for timeout adjustment: {e}")

            # Check if we've exceeded the current timeout
            if elapsed > current_timeout:
                print_error(f"ERROR: Workflow exceeded timeout of {current_timeout}s ({current_timeout//60} minutes)")
                process.kill()
                process.wait()  # Clean up zombie process
                returncode = -1
                break

            # Sleep briefly to avoid busy-waiting
            time.sleep(0.1)  # Shorter sleep since we're checking queue

        # Wait for threads to complete
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

        # Reconstruct stdout and stderr from collected lines
        stdout = ''.join(stdout_lines)
        stderr = ''.join(stderr_lines)

        # Create a result object similar to subprocess.run()
        class ProcessResult:
            def __init__(self, returncode, stdout, stderr):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        result = ProcessResult(returncode, stdout, stderr)
        print_debug(f"DEBUG: Return code: {result.returncode}")
        print_debug(f"DEBUG: Final timeout used: {current_timeout}s ({current_timeout//60} minutes)")

        # Report output statistics to track pipe buffer usage
        if stdout_stats or stderr_stats:
            print_info(f"INFO: 📊 Output Statistics (Pipe Buffer Usage):")
            if stdout_stats:
                stdout_kb = stdout_stats['bytes'] / 1024
                print_info(f"INFO:    stdout: {stdout_stats['lines']:,} lines, {stdout_kb:.2f} KB ({stdout_stats['bytes']:,} bytes)")
            if stderr_stats:
                stderr_kb = stderr_stats['bytes'] / 1024
                print_info(f"INFO:    stderr: {stderr_stats['lines']:,} lines, {stderr_kb:.2f} KB ({stderr_stats['bytes']:,} bytes)")

            total_bytes = (stdout_stats['bytes'] if stdout_stats else 0) + (stderr_stats['bytes'] if stderr_stats else 0)
            total_kb = total_bytes / 1024
            print_info(f"INFO:    Total: {total_kb:.2f} KB ({total_bytes:,} bytes)")

            # Warn if output is high
            if total_kb > 64:
                print_warning(f"INFO: ⚠️  Output volume ({total_kb:.2f} KB) exceeded typical pipe buffer size (64 KB)")
                print_warning(f"INFO: ⚠️  Without continuous pipe reading, this would have caused a deadlock!")

        # Calculate workflow execution time
        workflow_elapsed = time.time() - start_time

        if result.returncode == 0:
            print_success(f"INFO: Successfully triggered workflow '{workflow}' for issue #{issue_number}")
            print_success(f"INFO: ADW ID: {adw_id}")
            print_info(f"INFO: Workflow execution time: {workflow_elapsed:.1f} seconds")
            if result.stdout:
                print_debug(f"DEBUG: Output: {result.stdout[:500]}")  # First 500 chars
            return (True, workflow_elapsed)
        else:
            print_error(f"ERROR: Failed to trigger workflow '{workflow}' for issue #{issue_number}")
            print_error(f"ERROR: Return code: {result.returncode}")

            if result.stderr:
                print_error(f"ERROR: stderr output:")
                print_error(result.stderr)
            else:
                print_error(f"ERROR: No stderr output (empty or None)")

            if result.stdout:
                print_error(f"ERROR: stdout output:")
                print_error(result.stdout)
            else:
                print_error(f"ERROR: No stdout output (empty or None)")

            # Try to read execution logs for better error context
            # Orchestrator workflows (like adw_plan_build_iso) run phases that create their own logs
            # Look for any execution.log files in the ADW directory
            project_root = Path(__file__).parent.parent.parent
            adw_dir = project_root / "agents" / adw_id

            if adw_dir.exists():
                try:
                    # Find all execution.log files in this ADW directory
                    import glob
                    log_pattern = str(adw_dir / "*/execution.log")
                    log_files = glob.glob(log_pattern)

                    if log_files:
                        # Sort by modification time, most recent first
                        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

                        print_error(f"ERROR: Found {len(log_files)} execution log(s) in agents/{adw_id}/")

                        # Read the most recent log file
                        latest_log = log_files[0]
                        log_phase = Path(latest_log).parent.name

                        with open(latest_log, 'r') as f:
                            log_lines = f.readlines()

                        # Extract ERROR lines
                        errors = [line.strip() for line in log_lines if "ERROR" in line]

                        if errors:
                            print_error(f"ERROR: Errors from {log_phase}/execution.log:")
                            # Show last 10 error lines
                            for error in errors[-10:]:
                                print_error(f"  {error}")
                        else:
                            # No errors - show last 10 lines to see what happened
                            print_error(f"ERROR: Last activity from {log_phase}/execution.log:")
                            for line in log_lines[-10:]:
                                print_error(f"  {line.strip()}")

                        # Also list all log files for reference
                        if len(log_files) > 1:
                            print_debug(f"DEBUG: All execution logs found:")
                            for log_file in log_files:
                                phase = Path(log_file).parent.name
                                print_debug(f"  - agents/{adw_id}/{phase}/execution.log")
                    else:
                        print_debug(f"DEBUG: No execution.log files found in agents/{adw_id}/")
                except Exception as e:
                    print_debug(f"DEBUG: Could not read execution logs: {e}")
            else:
                print_debug(f"DEBUG: ADW directory not found at {adw_dir}")

            print_error(f"ERROR: Workflow execution time: {workflow_elapsed:.1f} seconds")
            return (False, workflow_elapsed)

    except subprocess.TimeoutExpired as e:
        print_error(f"ERROR: Workflow '{workflow}' timed out after {timeout} seconds for issue #{issue_number}")
        print_error(f"ERROR: {e}")

        # Try to read execution logs to see what was happening when timeout occurred
        # Orchestrator workflows run phases that create their own logs
        project_root = Path(__file__).parent.parent.parent
        adw_dir = project_root / "agents" / adw_id

        if adw_dir.exists():
            try:
                # Find all execution.log files in this ADW directory
                import glob
                log_pattern = str(adw_dir / "*/execution.log")
                log_files = glob.glob(log_pattern)

                if log_files:
                    # Sort by modification time, most recent first
                    log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

                    print_error(f"ERROR: Found {len(log_files)} execution log(s) - showing most recent activity:")

                    # Read the most recent log file
                    latest_log = log_files[0]
                    log_phase = Path(latest_log).parent.name

                    with open(latest_log, 'r') as f:
                        log_lines = f.readlines()

                    if log_lines:
                        print_error(f"ERROR: Last activity from {log_phase}/execution.log:")
                        # Show last 10 lines to see what was happening before timeout
                        for line in log_lines[-10:]:
                            print_error(f"  {line.strip()}")

                        # Check if this phase actually completed
                        last_line = log_lines[-1].strip() if log_lines else ""
                        if "completed successfully" in last_line.lower():
                            print_error(f"ERROR: Note: {log_phase} phase COMPLETED but orchestrator timed out")
                            print_error(f"ERROR: The subprocess finished after the {timeout}s timeout")
                            print_error(f"ERROR: Consider increasing timeout: --workflow-timeout {timeout * 2}")

                    # List all phases that ran
                    if len(log_files) > 1:
                        print_error(f"ERROR: Phases that executed:")
                        for log_file in log_files:
                            phase = Path(log_file).parent.name
                            print_error(f"  - {phase}")
                else:
                    print_debug(f"DEBUG: No execution.log files found in agents/{adw_id}/")
            except Exception as read_error:
                print_debug(f"DEBUG: Could not read execution logs: {read_error}")
        else:
            print_debug(f"DEBUG: ADW directory not found at {adw_dir}")

        # Timeout occurred - calculate elapsed time from when we started the subprocess
        timeout_elapsed = time.time() - start_time if 'start_time' in locals() else timeout
        print_error(f"ERROR: Workflow execution time at timeout: {timeout_elapsed:.1f} seconds")
        return (False, timeout_elapsed)
    except FileNotFoundError as e:
        print_error(f"ERROR: File not found error for issue #{issue_number}")
        print_error(f"ERROR: {e}")
        print_error(f"ERROR: Check that Python executable and script path are correct")
        return (False, 0.0)
    except Exception as e:
        print_error(f"ERROR: Exception while triggering workflow '{workflow}' for issue #{issue_number}")
        print_error(f"ERROR: Exception type: {type(e).__name__}")
        print_error(f"ERROR: Exception message: {e}")
        import traceback
        print_error(f"ERROR: Traceback:")
        traceback.print_exc()
        # Try to calculate elapsed time if subprocess was started
        exception_elapsed = time.time() - start_time if 'start_time' in locals() else 0.0
        return (False, exception_elapsed)


def check_and_process_issues():
    """Main function that checks for issues and processes qualifying ones."""
    if shutdown_requested:
        print_info(f"INFO: Shutdown requested, skipping check cycle")
        return

    start_time = time.time()
    print_info(f"INFO: Starting issue check cycle")
    print_status("Checking for new issues...")

    try:
        # Fetch all open issues
        issues = fetch_open_issues(REPO_PATH)

        if not issues:
            print_info(f"INFO: No open issues found")
            return

        # Track newly qualified issues with their workflow info
        new_qualifying_issues = []

        # Check each issue
        for issue in issues:
            issue_number = issue.number
            if not issue_number:
                continue

            # Skip if already processed in this session
            if issue_number in processed_issues:
                continue

            # Check if issue should be processed and get workflow info
            should_process, workflow, adw_id, model_set = should_process_issue(issue_number)
            if should_process:
                new_qualifying_issues.append({
                    "issue_number": issue_number,
                    "workflow": workflow,
                    "adw_id": adw_id,
                    "model_set": model_set,
                })

        # Process qualifying issues
        if new_qualifying_issues:
            issue_numbers = [qi["issue_number"] for qi in new_qualifying_issues]
            print_info(f"INFO: Found {len(new_qualifying_issues)} new qualifying issues: {issue_numbers}")

            for issue_info in new_qualifying_issues:
                if shutdown_requested:
                    print_info(f"INFO: Shutdown requested, stopping issue processing")
                    break

                issue_number = issue_info["issue_number"]
                workflow = issue_info["workflow"]
                adw_id = issue_info["adw_id"]
                model_set = issue_info["model_set"]

                # Track when processing starts for this issue
                issue_start_time = time.time()

                # Print BUSY status before triggering workflow
                print_status(f"BUSY - Processing issue #{issue_number} with workflow '{workflow}'")

                # Trigger the workflow with extracted info
                success, workflow_time = trigger_adw_workflow(issue_number, workflow, adw_id, model_set, workflow_timeout_seconds)

                # Calculate total cycle time for this issue
                cycle_elapsed = time.time() - issue_start_time

                if success:
                    processed_issues.add(issue_number)
                    # Log timing metrics for successful workflow
                    print_success(f"INFO: ✅ Workflow completed for issue #{issue_number}")
                    print_success(f"INFO:    Total cycle time: {cycle_elapsed:.1f} seconds")
                    print_success(f"INFO:    Workflow execution time: {workflow_time:.1f} seconds")
                    overhead = cycle_elapsed - workflow_time
                    print_info(f"INFO:    Trigger overhead: {overhead:.1f} seconds")
                    print_status(f"IDLE - Issue #{issue_number} processed successfully, ready for new issues")
                else:
                    # Log timing metrics for failed workflow
                    print_error(f"ERROR: ❌ Workflow failed for issue #{issue_number}")
                    print_error(f"ERROR:    Total cycle time: {cycle_elapsed:.1f} seconds")
                    print_error(f"ERROR:    Workflow execution time: {workflow_time:.1f} seconds")
                    print_warning(f"WARNING: Failed to process issue #{issue_number}, will retry in next cycle")
                    print_status(f"IDLE - Issue #{issue_number} processing failed, ready for new issues")
        else:
            print_info(f"INFO: No new qualifying issues found")
            print_status("IDLE - Waiting for new issues to process")

        # Log performance metrics
        cycle_time = time.time() - start_time
        print_info(f"INFO: Check cycle completed in {cycle_time:.2f} seconds")
        print_info(f"INFO: Total processed issues in session: {len(processed_issues)}")

        # Print status summary
        if len(new_qualifying_issues) > 0:
            print_status(f"Cycle complete - Processed {len(new_qualifying_issues)} issue(s)")
        else:
            print_status("Cycle complete - No issues processed, system IDLE")

    except Exception as e:
        print_error(f"ERROR: Error during check cycle: {e}")
        import traceback
        traceback.print_exc()


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments with rich formatting.

    Returns:
        argparse.Namespace: Parsed arguments with polling_interval and workflow_timeout
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=RichHelpFormatter,
        epilog="Example: trigger_cron.py --polling-interval 45 --workflow-timeout 600"
    )

    parser.add_argument(
        "-p", "--polling-interval",
        type=int,
        default=DEFAULT_POLLING_INTERVAL,
        metavar="SECONDS",
        help=f"Interval between GitHub polling cycles (default: {DEFAULT_POLLING_INTERVAL}s, range: {MIN_POLLING_INTERVAL}-{MAX_POLLING_INTERVAL}s)"
    )

    parser.add_argument(
        "-t", "--workflow-timeout",
        type=int,
        default=DEFAULT_WORKFLOW_TIMEOUT,
        metavar="SECONDS",
        help=f"Timeout for workflow execution (default: {DEFAULT_WORKFLOW_TIMEOUT}s / 30min, range: {MIN_WORKFLOW_TIMEOUT}-{MAX_WORKFLOW_TIMEOUT}s)"
    )

    args = parser.parse_args()

    # Validate polling interval
    if args.polling_interval < MIN_POLLING_INTERVAL or args.polling_interval > MAX_POLLING_INTERVAL:
        print_error(f"ERROR: Polling interval must be between {MIN_POLLING_INTERVAL} and {MAX_POLLING_INTERVAL} seconds")
        sys.exit(1)

    # Validate workflow timeout
    if args.workflow_timeout < MIN_WORKFLOW_TIMEOUT or args.workflow_timeout > MAX_WORKFLOW_TIMEOUT:
        print_error(f"ERROR: Workflow timeout must be between {MIN_WORKFLOW_TIMEOUT} and {MAX_WORKFLOW_TIMEOUT} seconds")
        sys.exit(1)

    return args


def main(polling_interval: int = DEFAULT_POLLING_INTERVAL, workflow_timeout: int = DEFAULT_WORKFLOW_TIMEOUT):
    """Main entry point for the cron trigger.

    Args:
        polling_interval: Seconds between GitHub polling cycles (default: 30)
        workflow_timeout: Timeout for workflow execution in seconds (default: 1800)
    """
    global workflow_timeout_seconds
    workflow_timeout_seconds = workflow_timeout

    print_info(f"INFO: Starting ADW cron trigger")
    print_info(f"INFO: Repository: {REPO_PATH}")
    print_info(f"INFO: Polling interval: {polling_interval} seconds")
    print_info(f"INFO: Workflow timeout: {workflow_timeout} seconds")

    # Validate ANTHROPIC_API_KEY at startup
    print_info("INFO: Validating ANTHROPIC_API_KEY...")
    success, error_msg = validate_anthropic_api_key()
    if not success:
        print_error(f"ERROR: {error_msg}")
        print_error("ERROR: Please set a valid ANTHROPIC_API_KEY environment variable")
        print_info("INFO: Export ANTHROPIC_API_KEY in your shell or add it to .env file")
        sys.exit(1)
    print_success("SUCCESS: ANTHROPIC_API_KEY validated successfully")

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Schedule the check function
    schedule.every(polling_interval).seconds.do(check_and_process_issues)

    # Run initial check immediately
    check_and_process_issues()

    # Main loop
    print_info(f"INFO: Entering main scheduling loop")
    while not shutdown_requested:
        schedule.run_pending()
        time.sleep(1)

    print_info(f"INFO: Shutdown complete")


if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_arguments()

    # Run main with parsed arguments
    main(polling_interval=args.polling_interval, workflow_timeout=args.workflow_timeout)