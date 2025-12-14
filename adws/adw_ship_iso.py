#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Ship Iso - AI Developer Workflow for shipping (merging) to main

Usage:
  uv run adw_ship_iso.py <issue-number> <adw-id>

Workflow:
1. Load state and validate worktree exists
2. Validate ALL state fields are populated (not None)
3. Perform manual git merge in main repository:
   - Fetch latest from origin
   - Checkout main
   - Merge feature branch
   - Push to origin/main
4. Post success message to issue

This workflow REQUIRES that all previous workflows have been run and that
every field in ADWState has a value. This is our final approval step.

Note: Merge operations happen in the main repository root, not in the worktree,
to preserve the worktree's state.
"""

import sys
import os
import logging
import json
import subprocess
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

from adw_modules.state import ADWState
from adw_modules.github import (
    make_issue_comment,
    get_repo_url,
    extract_repo_path,
)
from adw_modules.workflow_ops import format_issue_message
from adw_modules.utils import setup_logger, check_env_vars
from adw_modules.worktree_ops import validate_worktree
from adw_modules.data_types import ADWStateData
from adw_modules.execution_log import log_execution_start, log_execution_end

# Agent name constant
AGENT_SHIPPER = "shipper"


def get_main_repo_root() -> str:
    """Get the main repository root directory (parent of adws)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def manual_merge_to_main(branch_name: str, logger: logging.Logger) -> Tuple[bool, Optional[str]]:
    """Manually merge a branch to main using git commands."""
    repo_root = get_main_repo_root()
    logger.info(f"Performing manual merge in main repository: {repo_root}")

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=repo_root
        )
        original_branch = result.stdout.strip()
        logger.debug(f"Original branch: {original_branch}")

        logger.info("Fetching latest from origin...")
        result = subprocess.run(
            ["git", "fetch", "origin"],
            capture_output=True, text=True, cwd=repo_root
        )
        if result.returncode != 0:
            return False, f"Failed to fetch from origin: {result.stderr}"

        logger.info("Checking out main branch...")
        result = subprocess.run(
            ["git", "checkout", "main"],
            capture_output=True, text=True, cwd=repo_root
        )
        if result.returncode != 0:
            return False, f"Failed to checkout main: {result.stderr}"

        logger.info("Pulling latest main...")
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            capture_output=True, text=True, cwd=repo_root
        )
        if result.returncode != 0:
            subprocess.run(["git", "checkout", original_branch], cwd=repo_root)
            return False, f"Failed to pull latest main: {result.stderr}"

        logger.info(f"Merging branch {branch_name} (no-ff to preserve all commits)...")
        result = subprocess.run(
            ["git", "merge", branch_name, "--no-ff", "-m", f"Merge branch '{branch_name}' via ADW Ship workflow"],
            capture_output=True, text=True, cwd=repo_root
        )
        if result.returncode != 0:
            subprocess.run(["git", "checkout", original_branch], cwd=repo_root)
            return False, f"Failed to merge {branch_name}: {result.stderr}"

        logger.info("Pushing to origin/main...")
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            capture_output=True, text=True, cwd=repo_root
        )
        if result.returncode != 0:
            subprocess.run(["git", "checkout", original_branch], cwd=repo_root)
            return False, f"Failed to push to origin/main: {result.stderr}"

        logger.info(f"Restoring original branch: {original_branch}")
        subprocess.run(["git", "checkout", original_branch], cwd=repo_root)

        logger.info("Successfully merged and pushed to main!")
        return True, None

    except Exception as e:
        logger.error(f"Unexpected error during merge: {e}")
        try:
            subprocess.run(["git", "checkout", original_branch], cwd=repo_root)
        except:
            pass
        return False, str(e)


def validate_state_completeness(state: ADWState, logger: logging.Logger) -> tuple[bool, list[str]]:
    """Validate that all required fields in ADWState have values."""
    expected_fields = {
        "adw_id",
        "issue_number",
        "branch_name",
        "plan_file",
        "issue_class",
        "worktree_path",
        "backend_port",
        "frontend_port",
    }

    missing_fields = []

    for field in expected_fields:
        value = state.get(field)
        if value is None:
            missing_fields.append(field)
            logger.warning(f"Missing required field: {field}")
        else:
            logger.debug(f"✓ {field}: {value}")

    return len(missing_fields) == 0, missing_fields


def main():
    """Main entry point."""
    load_dotenv()

    if len(sys.argv) < 3:
        print("Usage: uv run adw_ship_iso.py <issue-number> <adw-id>")
        print("\nError: Both issue-number and adw-id are required")
        print("Run the complete SDLC workflow before shipping")
        sys.exit(1)

    issue_number = sys.argv[1]
    adw_id = sys.argv[2]

    temp_logger = setup_logger(adw_id, "adw_ship_iso")
    state = ADWState.load(adw_id, temp_logger)
    if not state:
        logger = setup_logger(adw_id, "adw_ship_iso")
        logger.error(f"No state found for ADW ID: {adw_id}")
        logger.error("Run the complete SDLC workflow before shipping")
        print(f"\nError: No state found for ADW ID: {adw_id}")
        print("Run the complete SDLC workflow before shipping")
        sys.exit(1)

    issue_number = state.get("issue_number", issue_number)

    state.append_adw_id("adw_ship_iso")

    logger = setup_logger(adw_id, "adw_ship_iso")
    logger.info(f"ADW Ship Iso starting - ID: {adw_id}, Issue: {issue_number}")

    worktree_path = state.get("worktree_path")
    start_entry = log_execution_start(
        script_name="adw_ship_iso.py",
        adw_id=adw_id,
        issue_number=issue_number,
        worktree_path=worktree_path,
    )

    exit_code = 0
    success = True
    error_info = None

    try:
        check_env_vars(logger)

        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, "ops", f"🚢 Starting ship workflow\n"
                               f"📋 Validating state completeness...")
        )

        logger.info("Validating state completeness...")
        is_valid, missing_fields = validate_state_completeness(state, logger)

        if not is_valid:
            error_msg = f"State validation failed. Missing fields: {', '.join(missing_fields)}"
            logger.error(error_msg)
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, AGENT_SHIPPER, f"❌ {error_msg}\n\n"
                                   "Please ensure all workflows have been run:\n"
                                   "- adw_plan_iso.py (creates plan_file, branch_name, issue_class)\n"
                                   "- adw_build_iso.py (implements the plan)\n"
                                   "- adw_test_iso.py (runs tests)\n"
                                   "- adw_review_iso.py (reviews implementation)\n"
                                   "- adw_document_iso.py (generates docs)")
            )
            sys.exit(1)

        logger.info("State validation passed - all fields have values")

        valid, error = validate_worktree(adw_id, state)
        if not valid:
            logger.error(f"Worktree validation failed: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, AGENT_SHIPPER, f"❌ Worktree validation failed: {error}")
            )
            sys.exit(1)

        worktree_path = state.get("worktree_path")
        logger.info(f"Worktree validated at: {worktree_path}")

        branch_name = state.get("branch_name")
        logger.info(f"Preparing to merge branch: {branch_name}")

        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, AGENT_SHIPPER, f"📋 State validation complete\n"
                               f"🔍 Preparing to merge branch: {branch_name}")
        )

        logger.info(f"Starting manual merge of {branch_name} to main...")
        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, AGENT_SHIPPER, f"🔀 Merging {branch_name} to main...\n"
                               "Using manual git operations in main repository")
        )

        merge_success, error = manual_merge_to_main(branch_name, logger)

        if not merge_success:
            logger.error(f"Failed to merge: {error}")
            make_issue_comment(
                issue_number,
                format_issue_message(adw_id, AGENT_SHIPPER, f"❌ Failed to merge: {error}")
            )
            sys.exit(1)

        logger.info(f"Successfully merged {branch_name} to main")

        make_issue_comment(
            issue_number,
            format_issue_message(adw_id, AGENT_SHIPPER,
                               f"🎉 **Successfully shipped!**\n\n"
                               f"✅ Validated all state fields\n"
                               f"✅ Merged branch `{branch_name}` to main\n"
                               f"✅ Pushed to origin/main\n\n"
                               f"🚢 Code has been deployed to production!")
        )

        state.save("adw_ship_iso")

        make_issue_comment(
            issue_number,
            f"{adw_id}_ops: 📋 Final ship state:\n```json\n{json.dumps(state.data, indent=2)}\n```"
        )

        logger.info("Ship workflow completed successfully")

    except SystemExit as e:
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
