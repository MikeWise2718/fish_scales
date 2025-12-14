#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Plan Build Review Iso - Compositional workflow for isolated planning, building, and reviewing

Usage: uv run adw_plan_build_review_iso.py <issue-number> [adw-id] [--skip-resolution]

This script runs:
1. adw_plan_iso.py - Planning phase (isolated)
2. adw_build_iso.py - Implementation phase (isolated)
3. adw_review_iso.py - Review phase (isolated)

The scripts are chained together via persistent state (adw_state.json).
"""

import subprocess
import sys
import os

# Add the parent directory to Python path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adw_modules.workflow_ops import ensure_adw_id
from adw_modules.execution_log import (
    log_execution_start,
    log_execution_end,
    track_subprocess_start,
    track_subprocess_end,
)


def main():
    """Main entry point."""
    # Check for --skip-resolution flag
    skip_resolution = "--skip-resolution" in sys.argv
    if skip_resolution:
        sys.argv.remove("--skip-resolution")

    if len(sys.argv) < 2:
        print("Usage: uv run adw_plan_build_review_iso.py <issue-number> [adw-id] [--skip-resolution]")
        print("\nThis runs the isolated plan, build, and review workflow:")
        print("  1. Plan (isolated)")
        print("  2. Build (isolated)")
        print("  3. Review (isolated)")
        sys.exit(1)

    issue_number = sys.argv[1]
    adw_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Ensure ADW ID exists with initialized state
    adw_id = ensure_adw_id(issue_number, adw_id)
    print(f"Using ADW ID: {adw_id}")

    # Start execution logging
    start_entry = log_execution_start(
        script_name="adw_plan_build_review_iso.py",
        adw_id=adw_id,
        issue_number=issue_number,
    )

    exit_code = 0
    success = True
    error_info = None
    subprocesses = []

    try:
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
            print("Isolated plan phase failed")
            sys.exit(1)

        # Run isolated build with the ADW ID
        build_cmd = ["uv", "run", os.path.join(script_dir, "adw_build_iso.py"), issue_number, adw_id]
        print(f"\n=== ISOLATED BUILD PHASE ===")
        print(f"Running: {' '.join(build_cmd)}")

        build_invocation = track_subprocess_start("adw_build_iso.py")
        build = subprocess.run(build_cmd)
        build_invocation = track_subprocess_end(build_invocation, build.returncode)
        subprocesses.append(build_invocation)

        if build.returncode != 0:
            print("Isolated build phase failed")
            sys.exit(1)

        # Run isolated review with the ADW ID
        review_cmd = ["uv", "run", os.path.join(script_dir, "adw_review_iso.py"), issue_number, adw_id]
        if skip_resolution:
            review_cmd.append("--skip-resolution")

        print(f"\n=== ISOLATED REVIEW PHASE ===")
        print(f"Running: {' '.join(review_cmd)}")

        review_invocation = track_subprocess_start("adw_review_iso.py")
        review = subprocess.run(review_cmd)
        review_invocation = track_subprocess_end(review_invocation, review.returncode)
        subprocesses.append(review_invocation)

        if review.returncode != 0:
            print("Isolated review phase failed")
            sys.exit(1)

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
