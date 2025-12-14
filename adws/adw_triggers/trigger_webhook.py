#!/usr/bin/env -S uv run
# /// script
# dependencies = ["fastapi", "uvicorn", "python-dotenv", "rich>=13.7.0", "rich-argparse>=1.4.0", "anthropic>=0.70.0"]
# ///

"""
GitHub Webhook Trigger - AI Developer Workflow (ADW)

FastAPI webhook endpoint that receives GitHub issue events and triggers ADW workflows.
Responds immediately to meet GitHub's 10-second timeout by launching workflows
in the background. Supports both standard and isolated workflows.

Configuration:
- Port: --port/-p (default: 8001, from PORT env var or argument)

Environment Requirements:
- PORT: Server port (default: 8001, can be overridden by --port argument)
- All workflow requirements (GITHUB_PAT, ANTHROPIC_API_KEY, etc.)
"""

import argparse
import os
import subprocess
import sys
from typing import Optional
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from rich_argparse import RichHelpFormatter
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adw_modules.utils import make_adw_id, setup_logger, get_safe_subprocess_env, validate_anthropic_api_key
from adw_modules.console import (
    print_info,
    print_success,
    print_warning,
    print_error,
    print_debug,
)
from adw_modules.github import make_issue_comment, ADW_BOT_IDENTIFIER
from adw_modules.workflow_ops import extract_adw_info, AVAILABLE_ADW_WORKFLOWS
from adw_modules.state import ADWState

# Load environment variables
load_dotenv()

# Port configuration constants
DEFAULT_PORT = int(os.getenv("PORT", "8001"))
MIN_PORT = 1024
MAX_PORT = 65535

# Dependent workflows that require existing worktrees
# These cannot be triggered directly via webhook
DEPENDENT_WORKFLOWS = [
    "adw_build_iso",
    "adw_test_iso",
    "adw_review_iso",
    "adw_document_iso",
    "adw_ship_iso",
]

# Create FastAPI app
app = FastAPI(
    title="ADW Webhook Trigger", description="GitHub webhook endpoint for ADW"
)


@app.post("/gh-webhook")
async def github_webhook(request: Request):
    """Handle GitHub webhook events."""
    try:
        # Get event type from header
        event_type = request.headers.get("X-GitHub-Event", "")

        # Parse webhook payload
        payload = await request.json()

        # Extract event details
        action = payload.get("action", "")
        issue = payload.get("issue", {})
        issue_number = issue.get("number")

        print_info(
            f"Received webhook: event={event_type}, action={action}, issue_number={issue_number}"
        )

        workflow = None
        provided_adw_id = None
        model_set = None
        trigger_reason = ""
        content_to_check = ""

        # Check if this is an issue opened event
        if event_type == "issues" and action == "opened" and issue_number:
            issue_body = issue.get("body", "")
            content_to_check = issue_body

            # Ignore issues from ADW bot to prevent loops
            if ADW_BOT_IDENTIFIER in issue_body:
                print_debug(f"Ignoring ADW bot issue to prevent loop")
                workflow = None
            # Check if body contains "adw_"
            elif "adw_" in issue_body.lower():
                # Use temporary ID for classification
                temp_id = make_adw_id()
                extraction_result = extract_adw_info(issue_body, temp_id)
                if extraction_result.has_workflow:
                    workflow = extraction_result.workflow_command
                    provided_adw_id = extraction_result.adw_id
                    model_set = extraction_result.model_set
                    trigger_reason = f"New issue with {workflow} workflow"

        # Check if this is an issue comment
        elif event_type == "issue_comment" and action == "created" and issue_number:
            comment = payload.get("comment", {})
            comment_body = comment.get("body", "")
            content_to_check = comment_body

            print_debug(f"Comment body: '{comment_body}'")

            # Ignore comments from ADW bot to prevent loops
            if ADW_BOT_IDENTIFIER in comment_body:
                print_debug(f"Ignoring ADW bot comment to prevent loop")
                workflow = None
            # Check if comment contains "adw_"
            elif "adw_" in comment_body.lower():
                # Use temporary ID for classification
                temp_id = make_adw_id()
                extraction_result = extract_adw_info(comment_body, temp_id)
                if extraction_result.has_workflow:
                    workflow = extraction_result.workflow_command
                    provided_adw_id = extraction_result.adw_id
                    model_set = extraction_result.model_set
                    trigger_reason = f"Comment with {workflow} workflow"

        # Validate workflow constraints
        if workflow in DEPENDENT_WORKFLOWS:
            if not provided_adw_id:
                print_error(
                    f"{workflow} is a dependent workflow that requires an existing ADW ID"
                )
                print_error(f"Cannot trigger {workflow} directly via webhook without ADW ID")
                workflow = None
                # Post error comment to issue
                try:
                    make_issue_comment(
                        str(issue_number),
                        f"❌ Error: `{workflow}` is a dependent workflow that requires an existing ADW ID.\n\n"
                        f"To run this workflow, you must provide the ADW ID in your comment, for example:\n"
                        f"`{workflow} adw-12345678`\n\n"
                        f"The ADW ID should come from a previous workflow run (like `adw_plan_iso` or `adw_patch_iso`).",
                    )
                except Exception as e:
                    print_error(f"Failed to post error comment: {e}")

        if workflow:
            # Use provided ADW ID or generate a new one
            adw_id = provided_adw_id or make_adw_id()

            # If ADW ID was provided, update/create state file
            if provided_adw_id:
                # Try to load existing state first
                state = ADWState.load(provided_adw_id)
                if state:
                    # Update issue_number and model_set if state exists
                    state.update(issue_number=str(issue_number), model_set=model_set)
                else:
                    # Only create new state if it doesn't exist
                    state = ADWState(provided_adw_id)
                    state.update(
                        adw_id=provided_adw_id,
                        issue_number=str(issue_number),
                        model_set=model_set,
                    )
                state.save("webhook_trigger")
            else:
                # Create new state for newly generated ADW ID
                state = ADWState(adw_id)
                state.update(
                    adw_id=adw_id, issue_number=str(issue_number), model_set=model_set
                )
                state.save("webhook_trigger")

            # Set up logger
            logger = setup_logger(adw_id, "webhook_trigger")
            logger.info(
                f"Detected workflow: {workflow} from content: {content_to_check[:100]}..."
            )
            if provided_adw_id:
                logger.info(f"Using provided ADW ID: {provided_adw_id}")

            # Post comment to issue about detected workflow
            try:
                make_issue_comment(
                    str(issue_number),
                    f"🤖 ADW Webhook: Detected `{workflow}` workflow request\n\n"
                    f"Starting workflow with ID: `{adw_id}`\n"
                    f"Workflow: `{workflow}` 🏗️\n"
                    f"Model Set: `{model_set}` ⚙️\n"
                    f"Reason: {trigger_reason}\n\n"
                    f"Logs will be available at: `agents/{adw_id}/{workflow}/`",
                )
            except Exception as e:
                logger.warning(f"Failed to post issue comment: {e}")

            # Build command to run the appropriate workflow
            script_dir = os.path.dirname(os.path.abspath(__file__))
            adws_dir = os.path.dirname(script_dir)
            repo_root = os.path.dirname(adws_dir)  # Go up to repository root
            trigger_script = os.path.join(adws_dir, f"{workflow}.py")

            print_info(f"INFO: Launching {workflow} for issue #{issue_number}")
            print_debug(f"DEBUG: Script directory: {script_dir}")
            print_debug(f"DEBUG: ADWs directory: {adws_dir}")
            print_debug(f"DEBUG: Repository root: {repo_root}")
            print_debug(f"DEBUG: Trigger script: {trigger_script}")

            # Verify script exists
            if not os.path.exists(trigger_script):
                error_msg = f"ERROR: Workflow script not found: {trigger_script}"
                print_error(error_msg)
                try:
                    make_issue_comment(
                        str(issue_number),
                        f"❌ Error: Workflow script `{workflow}.py` not found at expected location.\n\n"
                        f"Expected: `{trigger_script}`\n\n"
                        f"Please verify the workflow name is correct.",
                    )
                except Exception as e:
                    print_error(f"ERROR: Failed to post error comment: {e}")

                return {
                    "status": "error",
                    "issue": issue_number,
                    "message": f"Workflow script not found: {trigger_script}",
                }

            cmd = ["uv", "run", trigger_script, str(issue_number), adw_id]

            print_debug(f"DEBUG: Command: {' '.join(cmd)}")
            print_debug(f"DEBUG: Working directory: {repo_root}")
            print_debug(f"DEBUG: Reason: {trigger_reason}")

            try:
                # Get filtered environment
                filtered_env = get_safe_subprocess_env()
                print_debug(f"DEBUG: Environment variables count: {len(filtered_env)}")

                # Launch in background using Popen with filtered environment
                process = subprocess.Popen(
                    cmd,
                    cwd=repo_root,  # Run from repository root where .claude/commands/ is located
                    env=filtered_env,  # Pass only required environment variables
                    start_new_session=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                print_success(
                    f"INFO: Background process started for issue #{issue_number} with ADW ID: {adw_id}"
                )
                print_success(f"INFO: Process PID: {process.pid}")
                print_info(f"INFO: Logs will be written to: agents/{adw_id}/{workflow}/execution.log")

            except FileNotFoundError as e:
                error_msg = f"ERROR: File not found when launching workflow: {e}"
                print_error(error_msg)
                print_error(f"ERROR: Command was: {' '.join(cmd)}")
                print_error(f"ERROR: Check that 'uv' is in PATH and script exists")

                try:
                    make_issue_comment(
                        str(issue_number),
                        f"❌ Error: Failed to launch workflow - file not found.\n\n"
                        f"Command: `{' '.join(cmd)}`\n\n"
                        f"Error: `{e}`\n\n"
                        f"Please check that UV is installed and in PATH.",
                    )
                except Exception as comment_error:
                    print_error(f"ERROR: Failed to post error comment: {comment_error}")

                return {
                    "status": "error",
                    "issue": issue_number,
                    "message": f"File not found: {e}",
                }

            except PermissionError as e:
                error_msg = f"ERROR: Permission denied when launching workflow: {e}"
                print_error(error_msg)

                try:
                    make_issue_comment(
                        str(issue_number),
                        f"❌ Error: Permission denied when launching workflow.\n\n"
                        f"Error: `{e}`\n\n"
                        f"Please check file permissions.",
                    )
                except Exception as comment_error:
                    print_error(f"ERROR: Failed to post error comment: {comment_error}")

                return {
                    "status": "error",
                    "issue": issue_number,
                    "message": f"Permission denied: {e}",
                }

            except Exception as e:
                error_msg = f"ERROR: Unexpected error launching workflow: {type(e).__name__}: {e}"
                print_error(error_msg)
                import traceback
                print_error(f"ERROR: Traceback:")
                traceback.print_exc()

                try:
                    make_issue_comment(
                        str(issue_number),
                        f"❌ Error: Unexpected error launching workflow.\n\n"
                        f"Error type: `{type(e).__name__}`\n\n"
                        f"Error: `{e}`\n\n"
                        f"Check webhook server logs for details.",
                    )
                except Exception as comment_error:
                    print_error(f"ERROR: Failed to post error comment: {comment_error}")

                return {
                    "status": "error",
                    "issue": issue_number,
                    "message": f"Unexpected error: {e}",
                }

            # Return immediately
            return {
                "status": "accepted",
                "issue": issue_number,
                "adw_id": adw_id,
                "workflow": workflow,
                "message": f"ADW {workflow} triggered for issue #{issue_number}",
                "reason": trigger_reason,
                "logs": f"agents/{adw_id}/{workflow}/",
            }
        else:
            print_debug(
                f"Ignoring webhook: event={event_type}, action={action}, issue_number={issue_number}"
            )
            return {
                "status": "ignored",
                "reason": f"Not a triggering event (event={event_type}, action={action})",
            }

    except Exception as e:
        print_error(f"Error processing webhook: {e}")
        # Always return 200 to GitHub to prevent retries
        return {"status": "error", "message": "Internal error processing webhook"}


@app.get("/health")
async def health():
    """Health check endpoint - runs comprehensive system health check."""
    try:
        # Run the health check script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Health check is in adw_tests, not adw_triggers
        health_check_script = os.path.join(
            os.path.dirname(script_dir), "adw_tests", "health_check.py"
        )
        working_dir = os.path.dirname(script_dir)

        print_debug("DEBUG: Running health check")
        print_debug(f"DEBUG: Health check script: {health_check_script}")
        print_debug(f"DEBUG: Working directory: {working_dir}")

        # Verify health check script exists
        if not os.path.exists(health_check_script):
            error_msg = f"Health check script not found: {health_check_script}"
            print_error(f"ERROR: {error_msg}")
            return {
                "status": "unhealthy",
                "service": "adw-webhook-trigger",
                "error": error_msg,
            }

        # Run health check with timeout and filtered environment
        result = subprocess.run(
            ["uv", "run", health_check_script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=working_dir,  # Run from adws directory
            env=get_safe_subprocess_env(),
        )

        # Print the health check output for debugging
        print_debug("=== Health Check Output ===")
        print_debug(result.stdout)
        if result.stderr:
            print_debug("=== Health Check Errors ===")
            print_debug(result.stderr)
        print_debug(f"=== Health Check Return Code: {result.returncode} ===")

        # Parse the output - look for the overall status
        output_lines = result.stdout.strip().split("\n")
        is_healthy = result.returncode == 0

        # Extract key information from output
        warnings = []
        errors = []

        capturing_warnings = False
        capturing_errors = False

        for line in output_lines:
            if "⚠️  Warnings:" in line:
                capturing_warnings = True
                capturing_errors = False
                continue
            elif "❌ Errors:" in line:
                capturing_errors = True
                capturing_warnings = False
                continue
            elif "📝 Next Steps:" in line:
                break

            if capturing_warnings and line.strip().startswith("-"):
                warnings.append(line.strip()[2:])
            elif capturing_errors and line.strip().startswith("-"):
                errors.append(line.strip()[2:])

        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "service": "adw-webhook-trigger",
            "health_check": {
                "success": is_healthy,
                "warnings": warnings,
                "errors": errors,
                "details": "Run health_check.py directly for full report",
            },
        }

    except subprocess.TimeoutExpired as e:
        error_msg = f"Health check timed out after 30 seconds"
        print_error(f"ERROR: {error_msg}")
        return {
            "status": "unhealthy",
            "service": "adw-webhook-trigger",
            "error": error_msg,
        }
    except FileNotFoundError as e:
        error_msg = f"File not found when running health check: {e}"
        print_error(f"ERROR: {error_msg}")
        print_error(f"ERROR: Check that 'uv' is in PATH")
        return {
            "status": "unhealthy",
            "service": "adw-webhook-trigger",
            "error": error_msg,
        }
    except Exception as e:
        error_msg = f"Health check failed: {type(e).__name__}: {str(e)}"
        print_error(f"ERROR: {error_msg}")
        import traceback
        print_error(f"ERROR: Traceback:")
        traceback.print_exc()
        return {
            "status": "unhealthy",
            "service": "adw-webhook-trigger",
            "error": error_msg,
        }


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments with rich formatting.

    Returns:
        argparse.Namespace: Parsed arguments with port
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=RichHelpFormatter,
        epilog="Example: trigger_webhook.py --port 8080"
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=DEFAULT_PORT,
        metavar="PORT",
        help=f"Port to run the webhook server on (default: {DEFAULT_PORT}, range: {MIN_PORT}-{MAX_PORT})"
    )

    args = parser.parse_args()

    # Validate port
    if args.port < MIN_PORT or args.port > MAX_PORT:
        print_error(f"ERROR: Port must be between {MIN_PORT} and {MAX_PORT}")
        sys.exit(1)

    return args


if __name__ == "__main__":
    # Parse command-line arguments
    args = parse_arguments()
    port = args.port

    # Validate ANTHROPIC_API_KEY at startup
    print_info("INFO: Validating ANTHROPIC_API_KEY...")
    success, error_msg = validate_anthropic_api_key()
    if not success:
        print_error(f"ERROR: {error_msg}")
        print_error("ERROR: Please set a valid ANTHROPIC_API_KEY environment variable")
        print_info("INFO: Export ANTHROPIC_API_KEY in your shell or add it to .env file")
        sys.exit(1)
    print_success("SUCCESS: ANTHROPIC_API_KEY validated successfully")

    print_info(f"Starting server on http://0.0.0.0:{port}")
    print_info(f"Webhook endpoint: POST /gh-webhook")
    print_info(f"Health check: GET /health")

    uvicorn.run(app, host="0.0.0.0", port=port)
