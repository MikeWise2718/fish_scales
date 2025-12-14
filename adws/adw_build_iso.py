#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Build Iso - AI Developer Workflow for agentic building in isolated worktrees

Usage:
  uv run adw_build_iso.py <issue-number> <adw-id>

Workflow:
1. Load state and validate worktree exists
2. Find existing plan (from state)
3. Implement the solution based on plan in worktree
4. Commit implementation in worktree
5. Push and update PR

This workflow REQUIRES that adw_plan_iso.py or adw_patch_iso.py has been run first
to create the worktree. It cannot create worktrees itself.
"""

import sys
import os
import logging
import json
import subprocess
import time
from typing import Optional
from dotenv import load_dotenv

from adw_modules.state import ADWState
from adw_modules.git_ops import commit_changes, finalize_git_operations, get_current_branch
from adw_modules.github import fetch_issue, make_issue_comment, get_repo_url, extract_repo_path
from adw_modules.workflow_ops import (
    implement_plan,
    create_commit,
    format_issue_message,
    post_workflow_completion_summary,
    AGENT_IMPLEMENTOR,
)
from adw_modules.utils import setup_logger, check_env_vars
from adw_modules.data_types import GitHubIssue
from adw_modules.worktree_ops import validate_worktree
from adw_modules.execution_log import log_execution_start, log_execution_end




def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    # Parse command line args
    # INTENTIONAL: adw-id is REQUIRED - we need it to find the worktree
    if len(sys.argv) < 3:
        print("Usage: uv run adw_build_iso.py <issue-number> <adw-id>")
        print("\nError: adw-id is required to locate the worktree and plan file")
        print("Run adw_plan_iso.py or adw_patch_iso.py first to create the worktree")
        sys.exit(1)

    issue_number = sys.argv[1]
    adw_id = sys.argv[2]

    # Try to load existing state
    temp_logger = setup_logger(adw_id, "adw_build_iso")
    state = ADWState.load(adw_id, temp_logger)
    if state:
        # Found existing state - use the issue number from state if available
        issue_number = state.get("issue_number", issue_number)
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", "🔧 Build phase starting - loaded state from planning phase")
        )
    else:
        # No existing state found
        logger = setup_logger(adw_id, "adw_build_iso")
        logger.error(f"No state found for ADW ID: {adw_id}")
        logger.error("Run adw_plan_iso.py first to create the worktree and state")
        print(f"\nError: No state found for ADW ID: {adw_id}")
        print("Run adw_plan_iso.py first to create the worktree and state")
        sys.exit(1)

    # Track that this ADW workflow has run
    state.append_adw_id("adw_build_iso")

    # Set up logger with ADW ID from command line
    logger = setup_logger(adw_id, "adw_build_iso")
    logger.info(f"ADW Build Iso starting - ID: {adw_id}, Issue: {issue_number}")

    # Start execution logging
    worktree_path = state.get("worktree_path")
    start_entry = log_execution_start(
        script_name="adw_build_iso.py",
        adw_id=adw_id,
        issue_number=issue_number,
        worktree_path=worktree_path,
    )

    exit_code = 0
    success = True
    error_info = None

    try:
        # Post validation start message
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", "🔍 Validating environment and worktree...")
        )

        # Validate environment
        check_env_vars(logger)

        # Validate worktree exists
        valid, error = validate_worktree(adw_id, state)
        if not valid:
            logger.error(f"Worktree validation failed: {error}")
            logger.error("Run adw_plan_iso.py or adw_patch_iso.py first")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "ops", f"❌ Worktree validation failed: {error}\n"
                                   "Run adw_plan_iso.py or adw_patch_iso.py first")
            )
            sys.exit(1)

        # Get worktree path for explicit context
        worktree_path = state.get("worktree_path")
        logger.info(f"Using worktree at: {worktree_path}")

        # Get repo information
        try:
            github_repo_url = get_repo_url()
            repo_path = extract_repo_path(github_repo_url)
        except ValueError as e:
            logger.error(f"Error getting repository URL: {e}")
            sys.exit(1)

        # Ensure we have required state fields
        if not state.get("branch_name"):
            error_msg = "No branch name in state - run adw_plan_iso.py first"
            logger.error(error_msg)
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "ops", f"❌ {error_msg}")
            )
            sys.exit(1)

        if not state.get("plan_file"):
            error_msg = "No plan file in state - run adw_plan_iso.py first"
            logger.error(error_msg)
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "ops", f"❌ {error_msg}")
            )
            sys.exit(1)

        # Get port information for display
        backend_port = state.get("backend_port", "9100")
        frontend_port = state.get("frontend_port", "9200")

        # Post validation success
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", f"✅ Environment validated\n"
                               f"🏠 Worktree: {worktree_path}\n"
                               f"🔌 Ports - Backend: {backend_port}, Frontend: {frontend_port}")
        )

        # Checkout the branch in the worktree
        branch_name = state.get("branch_name")

        # Check current branch first to avoid unnecessary checkout
        logger.info(f"Checking current branch in worktree...")
        start_check = time.time()
        current_branch = get_current_branch(cwd=worktree_path, timeout=30)
        check_duration = time.time() - start_check

        if current_branch is None:
            # Branch check failed/timed out - proceed with checkout anyway
            logger.warning(f"Could not determine current branch (took {check_duration:.2f}s)")
            logger.warning("This may indicate filesystem performance issues or antivirus interference")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "ops", f"⚠️ Could not check current branch ({check_duration:.1f}s timeout), proceeding with checkout")
            )
            should_checkout = True
        elif current_branch == branch_name:
            logger.info(f"Current branch check took {check_duration:.2f}s - Already on: {current_branch}")
            logger.info(f"Already on branch {branch_name}, skipping checkout")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "ops", f"✅ Already on branch: {branch_name} (checkout skipped, saved time)")
            )
            should_checkout = False
        else:
            logger.info(f"Current branch check took {check_duration:.2f}s - Currently on: {current_branch}")
            logger.info(f"Need to checkout from '{current_branch}' to '{branch_name}'")
            should_checkout = True

        if should_checkout:
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, "ops", f"🔀 Checking out branch: {branch_name}")
            )

            start_checkout = time.time()
            try:
                result = subprocess.run(
                    ["git", "checkout", branch_name],
                    capture_output=True,
                    text=True,
                    cwd=worktree_path,
                    timeout=300,  # 5 minute timeout
                    check=True
                )
                checkout_duration = time.time() - start_checkout
                logger.info(f"Git checkout took {checkout_duration:.2f}s ({checkout_duration/60:.1f} minutes)")

                make_issue_comment(
                    issue_number,
                    format_issue_message(adw_id, "ops", f"✅ Branch checked out: {branch_name} (took {checkout_duration:.1f}s)")
                )

            except subprocess.TimeoutExpired:
                checkout_duration = time.time() - start_checkout
                error_msg = f"Git checkout timed out after {checkout_duration:.1f}s"
                logger.error(error_msg)

                suggestions = [
                    "**Possible causes and solutions:**",
                    "1. **Windows Defender** - Add exclusions for the worktree:",
                    f"   ```powershell",
                    f"   Add-MpPreference -ExclusionPath \"{worktree_path}\"",
                    f"   Add-MpPreference -ExclusionPath \"D:\\python\\scipap\\trees\"",
                    f"   ```",
                    f"   Run: `adws/check_defender_exclusions.ps1` (as Administrator)",
                    "",
                    "2. **Large .venv directory** - Ensure .venv is in .gitignore",
                    f"   Check if .venv is tracked: `cd {worktree_path} && git status .venv/`",
                    "",
                    "3. **Filesystem performance** - Check disk I/O:",
                    "   - Close other programs accessing the filesystem",
                    "   - Check Windows Task Manager for high disk usage",
                    "",
                    "4. **Git index lock** - Remove stale lock files:",
                    f"   ```bash",
                    f"   rm -f {worktree_path}/.git/index.lock",
                    f"   ```",
                    "",
                    "5. **Try manual checkout** to diagnose:",
                    f"   ```bash",
                    f"   cd {worktree_path}",
                    f"   time git checkout {branch_name}",
                    f"   ```"
                ]

                make_issue_comment(
                    issue_number,
                    format_issue_message(adw_id, "ops", f"❌ {error_msg}\n\n" + "\n".join(suggestions))
                )
                sys.exit(1)

            except subprocess.CalledProcessError as e:
                error_details = e.stderr if e.stderr else str(e)
                logger.error(f"Failed to checkout branch {branch_name}: {error_details}")

                suggestions = [
                    "**Git checkout failed. Try these solutions:**",
                    f"1. **Check if branch exists**: `cd {worktree_path} && git branch -a | grep {branch_name}`",
                    f"2. **Fetch latest changes**: `cd {worktree_path} && git fetch origin`",
                    f"3. **Clean working directory**: `cd {worktree_path} && git status` (check for uncommitted changes)",
                    f"4. **Force checkout**: `cd {worktree_path} && git checkout -f {branch_name}`",
                    "",
                    f"**Error details:** {error_details}"
                ]

                make_issue_comment(
                    issue_number,
                    format_issue_message(adw_id, "ops", "❌ Branch checkout failed\n\n" + "\n".join(suggestions))
                )
                sys.exit(1)

        # Get the plan file from state
        plan_file = state.get("plan_file")
        logger.info(f"Using plan file: {plan_file}")

        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", f"📋 Ready to implement - using plan: {plan_file}")
        )

        # Implement the plan (executing in worktree)
        logger.info("Implementing solution in worktree")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, AGENT_IMPLEMENTOR, "✅ Implementing solution in isolated environment")
        )

        implement_response = implement_plan(plan_file, adw_id, logger, working_dir=worktree_path)

        if not implement_response.success:
            logger.error(f"Error implementing solution: {implement_response.output}")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, AGENT_IMPLEMENTOR, f"❌ Error implementing solution: {implement_response.output}")
            )
            sys.exit(1)

        logger.debug(f"Implementation response: {implement_response.output}")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, AGENT_IMPLEMENTOR, "✅ Solution implemented")
        )

        # Fetch issue data for commit message generation
        logger.info("Fetching issue data for commit message")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", "📝 Preparing to commit changes...")
        )
        issue = fetch_issue(issue_number, repo_path)

        # Get issue classification from state or classify if needed
        issue_command = state.get("issue_class")
        if not issue_command:
            logger.info("No issue classification in state, running classify_issue")
            from adw_modules.workflow_ops import classify_issue
            issue_command, error = classify_issue(issue, adw_id, logger)
            if error:
                logger.error(f"Error classifying issue: {error}")
                # Default to feature if classification fails
                issue_command = "/feature"
                logger.warning("Defaulting to /feature after classification error")
            else:
                # Save the classification for future use
                state.update(issue_class=issue_command)
                state.save("adw_build_iso")

        # Create commit message
        logger.info("Creating implementation commit")
        commit_msg, error = create_commit(AGENT_IMPLEMENTOR, issue, issue_command, adw_id, logger, worktree_path)

        if error:
            logger.error(f"Error creating commit message: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, AGENT_IMPLEMENTOR, f"❌ Error creating commit message: {error}")
            )
            sys.exit(1)

        # Commit the implementation (in worktree)
        commit_success, error = commit_changes(commit_msg, cwd=worktree_path)

        if not commit_success:
            logger.error(f"Error committing implementation: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, AGENT_IMPLEMENTOR, f"❌ Error committing implementation: {error}")
            )
            sys.exit(1)

        logger.info(f"Committed implementation: {commit_msg}")
        make_issue_comment(
            issue_number, format_issue_message(adw_id, AGENT_IMPLEMENTOR, "✅ Implementation committed")
        )

        # Finalize git operations (push and PR)
        # Note: This will work from the worktree context
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", "🚀 Pushing changes to remote repository...")
        )
        finalize_git_operations(state, logger, cwd=worktree_path)

        logger.info("Build phase completed successfully")

        # Save final state
        state.save("adw_build_iso")

        # Post completion summary to issue
        post_workflow_completion_summary(
            issue_number=issue_number,
            adw_id=adw_id,
            workflow_name="Implementation",
            status="success",
            artifacts={
                "implementation": "Changes committed and pushed",
                "branch": state.get("branch_name")
            },
            next_steps=[
                f"Review the changes in the worktree: `{worktree_path}`",
                f"Check the pull request for implementation details",
                f"To run tests: `uv run adws/adw_test_iso.py {issue_number} {adw_id}`"
            ],
            worktree_path=worktree_path
        )

    except SystemExit as e:
        # Capture sys.exit() calls
        exit_code = e.code if isinstance(e.code, int) else 1
        success = exit_code == 0
        if not success:
            error_info = ("SystemExit", f"Script exited with code {exit_code}")
        raise
    except Exception as e:
        exit_code = 1
        success = False
        error_info = (type(e).__name__, str(e))
        raise
    finally:
        # Log execution end
        log_execution_end(
            start_entry=start_entry,
            exit_code=exit_code,
            success=success,
            error_type=error_info[0] if error_info else None,
            error_message=error_info[1] if error_info else None,
            model_set=state.get("model_set") if state else None,
        )


if __name__ == "__main__":
    main()
