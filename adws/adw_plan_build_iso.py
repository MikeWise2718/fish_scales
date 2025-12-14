#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Plan Build Iso - Compositional workflow for isolated planning and building

Usage: uv run adw_plan_build_iso.py <issue-number> [adw-id]

This script runs:
1. adw_plan_iso.py - Planning phase (isolated)
2. adw_build_iso.py - Implementation phase (isolated)

The scripts are chained together via persistent state (adw_state.json).
"""

import subprocess
import sys
import os

# Add the parent directory to Python path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adw_modules.workflow_ops import ensure_adw_id
from adw_modules.github import make_issue_comment
from adw_modules.utils import get_local_timestamp
from adw_modules.execution_log import (
    log_execution_start,
    log_execution_end,
    track_subprocess_start,
    track_subprocess_end,
)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run adw_plan_build_iso.py <issue-number> [adw-id]")
        print("\nThis runs the isolated plan and build workflow:")
        print("  1. Plan (isolated)")
        print("  2. Build (isolated)")
        sys.exit(1)

    issue_number = sys.argv[1]
    adw_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Ensure ADW ID exists with initialized state
    adw_id = ensure_adw_id(issue_number, adw_id)
    print(f"Using ADW ID: {adw_id}")

    # Start execution logging
    start_entry = log_execution_start(
        script_name="adw_plan_build_iso.py",
        adw_id=adw_id,
        issue_number=issue_number,
    )

    exit_code = 0
    success = True
    error_info = None
    subprocesses = []

    try:
        # Post workflow start notification
        try:
            timestamp = get_local_timestamp()
            make_issue_comment(
                issue_number,
                f"🤖 **ADW Plan+Build Workflow Started**\n\n"
                f"**Timestamp:** {timestamp}\n"
                f"**ADW ID:** `{adw_id}`\n"
                f"**Workflow:** Plan → Build\n\n"
                f"📋 Phase 1/2: Planning..."
            )
        except Exception as e:
            print(f"WARNING: Failed to post start comment to issue: {e}")

        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Run isolated plan with the ADW ID
        plan_cmd = ["uv", "run", os.path.join(script_dir, "adw_plan_iso.py"), issue_number, adw_id]
        print(f"\n=== ISOLATED PLAN PHASE ===")
        print(f"Running: {' '.join(plan_cmd)}")

        plan_invocation = track_subprocess_start("adw_plan_iso.py")
        plan = subprocess.run(plan_cmd)
        plan_invocation = track_subprocess_end(plan_invocation, plan.returncode)
        subprocesses.append(plan_invocation)

        if plan.returncode != 0:
            timestamp = get_local_timestamp()
            error_msg = (
                f"❌ **ADW Plan Phase Failed**\n\n"
                f"**Timestamp:** {timestamp}\n"
                f"**ADW ID:** `{adw_id}`\n"
                f"**Phase:** Planning\n"
                f"**Return Code:** {plan.returncode}\n\n"
                f"**Error:** The planning phase failed to complete successfully.\n\n"
                f"**Logs:** Check `agents/{adw_id}/planner/raw_output.jsonl` for details."
            )
            print(error_msg)
            try:
                make_issue_comment(issue_number, error_msg)
            except Exception as e:
                print(f"ERROR: Failed to post error comment to issue: {e}")
            sys.exit(1)

        # Post plan success and build start notification
        try:
            timestamp = get_local_timestamp()
            make_issue_comment(
                issue_number,
                f"✅ **Plan Phase Completed**\n\n"
                f"**Timestamp:** {timestamp}\n"
                f"**ADW ID:** `{adw_id}`\n\n"
                f"🔨 Phase 2/2: Building implementation..."
            )
        except Exception as e:
            print(f"WARNING: Failed to post plan success comment to issue: {e}")

        # Run isolated build with the ADW ID
        build_cmd = ["uv", "run", os.path.join(script_dir, "adw_build_iso.py"), issue_number, adw_id]
        print(f"\n=== ISOLATED BUILD PHASE ===")
        print(f"Running: {' '.join(build_cmd)}")

        build_invocation = track_subprocess_start("adw_build_iso.py")
        build = subprocess.run(build_cmd)
        build_invocation = track_subprocess_end(build_invocation, build.returncode)
        subprocesses.append(build_invocation)

        if build.returncode != 0:
            timestamp = get_local_timestamp()
            error_msg = (
                f"❌ **ADW Build Phase Failed**\n\n"
                f"**Timestamp:** {timestamp}\n"
                f"**ADW ID:** `{adw_id}`\n"
                f"**Phase:** Implementation\n"
                f"**Return Code:** {build.returncode}\n\n"
                f"**Error:** The implementation phase failed to complete successfully.\n\n"
                f"**Status:** Plan was created successfully, but implementation failed.\n\n"
                f"**Logs:** Check `agents/{adw_id}/implementor/raw_output.jsonl` for details."
            )
            print(error_msg)
            try:
                make_issue_comment(issue_number, error_msg)
            except Exception as e:
                print(f"ERROR: Failed to post error comment to issue: {e}")
            sys.exit(1)

        # Post final success notification
        try:
            timestamp = get_local_timestamp()
            make_issue_comment(
                issue_number,
                f"✅ **ADW Plan+Build Workflow Completed**\n\n"
                f"**Timestamp:** {timestamp}\n"
                f"**ADW ID:** `{adw_id}`\n"
                f"**Status:** All phases completed successfully! 🎉\n\n"
                f"**Phases Completed:**\n"
                f"- ✅ Planning\n"
                f"- ✅ Implementation\n\n"
                f"**Next Steps:**\n"
                f"- Review the changes in the worktree: `trees/{adw_id}/`\n"
                f"- Check the pull request for the implementation\n"
                f"- To run tests: `uv run adws/adw_test_iso.py {issue_number} {adw_id}`"
            )
        except Exception as e:
            print(f"WARNING: Failed to post success comment to issue: {e}")

        print(f"\n=== ISOLATED WORKFLOW COMPLETED ===")
        print(f"ADW ID: {adw_id}")
        print(f"All phases completed successfully!")

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
            subprocesses=subprocesses,
        )


if __name__ == "__main__":
    main()
