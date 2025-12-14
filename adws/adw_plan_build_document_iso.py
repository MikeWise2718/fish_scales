#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW Plan Build Document Iso - Compositional workflow for isolated planning, building, and documentation

Usage: uv run adw_plan_build_document_iso.py <issue-number> [adw-id]

This script runs:
1. adw_plan_iso.py - Planning phase (isolated)
2. adw_build_iso.py - Implementation phase (isolated)
3. adw_document_iso.py - Documentation phase (isolated)

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
    if len(sys.argv) < 2:
        print("Usage: uv run adw_plan_build_document_iso.py <issue-number> [adw-id]")
        print("\nThis runs the isolated plan, build, and document workflow:")
        print("  1. Plan (isolated)")
        print("  2. Build (isolated)")
        print("  3. Document (isolated)")
        sys.exit(1)

    issue_number = sys.argv[1]
    adw_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Ensure ADW ID exists with initialized state
    adw_id = ensure_adw_id(issue_number, adw_id)
    print(f"Using ADW ID: {adw_id}")

    # Start execution logging
    start_entry = log_execution_start(
        script_name="adw_plan_build_document_iso.py",
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

        # Run isolated documentation with the ADW ID
        document_cmd = ["uv", "run", os.path.join(script_dir, "adw_document_iso.py"), issue_number, adw_id]
        print(f"\n=== ISOLATED DOCUMENTATION PHASE ===")
        print(f"Running: {' '.join(document_cmd)}")

        document_invocation = track_subprocess_start("adw_document_iso.py")
        document = subprocess.run(document_cmd)
        document_invocation = track_subprocess_end(document_invocation, document.returncode)
        subprocesses.append(document_invocation)

        if document.returncode != 0:
            print("Isolated documentation phase failed")
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
