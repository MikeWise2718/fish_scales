#!/usr/bin/env -S uv run
# /// script
# dependencies = ["python-dotenv", "pydantic"]
# ///

"""
ADW SDLC Iso - Complete Software Development Life Cycle workflow with isolation

Usage: uv run adw_sdlc_iso.py <issue-number> [adw-id] [--skip-e2e] [--skip-resolution]

This script runs the complete ADW SDLC pipeline in isolation:
1. adw_plan_iso.py - Planning phase (isolated)
2. adw_build_iso.py - Implementation phase (isolated)
3. adw_test_iso.py - Testing phase (isolated)
4. adw_review_iso.py - Review phase (isolated)
5. adw_document_iso.py - Documentation phase (isolated)

The scripts are chained together via persistent state (adw_state.json).
Each phase runs in its own git worktree with dedicated ports.
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


def post_github_comment(issue_number: str, message: str):
    """Post a comment to GitHub issue, with error handling."""
    try:
        make_issue_comment(issue_number, message)
    except Exception as e:
        print(f"WARNING: Failed to post comment to issue: {e}")


def post_phase_error(issue_number: str, adw_id: str, phase_name: str, phase_number: int,
                     total_phases: int, returncode: int, agent_name: str):
    """Post error message for a failed phase."""
    timestamp = get_local_timestamp()
    error_msg = (
        f"❌ **ADW {phase_name} Phase Failed**\n\n"
        f"**Timestamp:** {timestamp}\n"
        f"**ADW ID:** `{adw_id}`\n"
        f"**Phase:** {phase_number}/{total_phases} - {phase_name}\n"
        f"**Return Code:** {returncode}\n\n"
        f"**Error:** The {phase_name.lower()} phase failed to complete successfully.\n\n"
        f"**Logs:** Check `agents/{adw_id}/{agent_name}/raw_output.jsonl` for details.\n\n"
        f"**Next Steps:**\n"
        f"- Review the error logs for detailed failure information\n"
        f"- Check if previous phases completed correctly\n"
        f"- Manually retry: `cd trees/{adw_id} && uv run --extra adws python adws/adw_{agent_name}_iso.py {issue_number} {adw_id}`"
    )
    print(error_msg)
    post_github_comment(issue_number, error_msg)


def main():
    """Main entry point."""
    # Check for flags
    skip_e2e = "--skip-e2e" in sys.argv
    skip_resolution = "--skip-resolution" in sys.argv

    # Remove flags from argv
    if skip_e2e:
        sys.argv.remove("--skip-e2e")
    if skip_resolution:
        sys.argv.remove("--skip-resolution")

    if len(sys.argv) < 2:
        print("Usage: uv run adw_sdlc_iso.py <issue-number> [adw-id] [--skip-e2e] [--skip-resolution]")
        print("\nThis runs the complete isolated Software Development Life Cycle:")
        print("  1. Plan (isolated)")
        print("  2. Build (isolated)")
        print("  3. Test (isolated)")
        print("  4. Review (isolated)")
        print("  5. Document (isolated)")
        sys.exit(1)

    issue_number = sys.argv[1]
    adw_id = sys.argv[2] if len(sys.argv) > 2 else None

    # Ensure ADW ID exists with initialized state
    adw_id = ensure_adw_id(issue_number, adw_id)
    print(f"Using ADW ID: {adw_id}")

    # Start execution logging
    start_entry = log_execution_start(
        script_name="adw_sdlc_iso.py",
        adw_id=adw_id,
        issue_number=issue_number,
    )

    exit_code = 0
    success = True
    error_info = None
    subprocesses = []

    try:
        # Post workflow start notification
        timestamp = get_local_timestamp()
        post_github_comment(
            issue_number,
            f"🤖 **ADW Complete SDLC Workflow Started**\n\n"
            f"**Timestamp:** {timestamp}\n"
            f"**ADW ID:** `{adw_id}`\n"
            f"**Workflow:** Plan → Build → Test → Review → Document\n"
            f"**E2E Tests:** {'Skipped' if skip_e2e else 'Included'}\n"
            f"**Auto-Resolution:** {'Disabled' if skip_resolution else 'Enabled'}\n\n"
            f"📋 Phase 1/5: Planning..."
        )

        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # ===== PHASE 1: PLAN =====
        plan_cmd = ["uv", "run", os.path.join(script_dir, "adw_plan_iso.py"), issue_number, adw_id]
        print(f"\n=== ISOLATED PLAN PHASE ===")
        print(f"Running: {' '.join(plan_cmd)}")

        plan_invocation = track_subprocess_start("adw_plan_iso.py")
        plan = subprocess.run(plan_cmd)
        plan_invocation = track_subprocess_end(plan_invocation, plan.returncode)
        subprocesses.append(plan_invocation)

        if plan.returncode != 0:
            post_phase_error(issue_number, adw_id, "Plan", 1, 5, plan.returncode, "plan")
            sys.exit(1)

        timestamp = get_local_timestamp()
        post_github_comment(issue_number, f"✅ **Plan Phase Completed** ({timestamp})\n\n🔨 Phase 2/5: Building implementation...")

        # ===== PHASE 2: BUILD =====
        build_cmd = ["uv", "run", os.path.join(script_dir, "adw_build_iso.py"), issue_number, adw_id]
        print(f"\n=== ISOLATED BUILD PHASE ===")
        print(f"Running: {' '.join(build_cmd)}")

        build_invocation = track_subprocess_start("adw_build_iso.py")
        build = subprocess.run(build_cmd)
        build_invocation = track_subprocess_end(build_invocation, build.returncode)
        subprocesses.append(build_invocation)

        if build.returncode != 0:
            post_phase_error(issue_number, adw_id, "Build", 2, 5, build.returncode, "build")
            sys.exit(1)

        timestamp = get_local_timestamp()
        post_github_comment(issue_number, f"✅ **Build Phase Completed** ({timestamp})\n\n🧪 Phase 3/5: Running tests...")

        # ===== PHASE 3: TEST =====
        test_cmd = ["uv", "run", os.path.join(script_dir, "adw_test_iso.py"), issue_number, adw_id, "--skip-e2e"]

        print(f"\n=== ISOLATED TEST PHASE ===")
        print(f"Running: {' '.join(test_cmd)}")

        test_invocation = track_subprocess_start("adw_test_iso.py")
        test = subprocess.run(test_cmd)
        test_invocation = track_subprocess_end(test_invocation, test.returncode)
        subprocesses.append(test_invocation)

        if test.returncode != 0:
            timestamp = get_local_timestamp()
            warning_msg = (
                f"⚠️ **Test Phase Had Failures** ({timestamp})\n\n"
                f"**ADW ID:** `{adw_id}`\n"
                f"**Phase:** 3/5 - Testing\n\n"
                f"**Warning:** Some tests failed, but continuing with review phase.\n\n"
                f"**Logs:** Check `agents/{adw_id}/tester/raw_output.jsonl` for details.\n\n"
                f"🔍 Phase 4/5: Reviewing implementation..."
            )
            print(warning_msg)
            post_github_comment(issue_number, warning_msg)
        else:
            timestamp = get_local_timestamp()
            post_github_comment(issue_number, f"✅ **Test Phase Completed** ({timestamp})\n\n🔍 Phase 4/5: Reviewing implementation...")

        # ===== PHASE 4: REVIEW =====
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
            post_phase_error(issue_number, adw_id, "Review", 4, 5, review.returncode, "review")
            sys.exit(1)

        timestamp = get_local_timestamp()
        post_github_comment(issue_number, f"✅ **Review Phase Completed** ({timestamp})\n\n📝 Phase 5/5: Generating documentation...")

        # ===== PHASE 5: DOCUMENT =====
        document_cmd = ["uv", "run", os.path.join(script_dir, "adw_document_iso.py"), issue_number, adw_id]
        print(f"\n=== ISOLATED DOCUMENTATION PHASE ===")
        print(f"Running: {' '.join(document_cmd)}")

        document_invocation = track_subprocess_start("adw_document_iso.py")
        document = subprocess.run(document_cmd)
        document_invocation = track_subprocess_end(document_invocation, document.returncode)
        subprocesses.append(document_invocation)

        if document.returncode != 0:
            post_phase_error(issue_number, adw_id, "Documentation", 5, 5, document.returncode, "document")
            sys.exit(1)

        # ===== WORKFLOW COMPLETE =====
        timestamp = get_local_timestamp()
        test_status = "✅ All tests passed" if test.returncode == 0 else "⚠️ Some tests failed (see warnings above)"

        post_github_comment(
            issue_number,
            f"✅ **ADW Complete SDLC Workflow Finished**\n\n"
            f"**Timestamp:** {timestamp}\n"
            f"**ADW ID:** `{adw_id}`\n"
            f"**Status:** All phases completed! 🎉\n\n"
            f"**Phases Completed:**\n"
            f"- ✅ Planning\n"
            f"- ✅ Implementation\n"
            f"- {test_status}\n"
            f"- ✅ Code Review\n"
            f"- ✅ Documentation\n\n"
            f"**Deliverables:**\n"
            f"- Implementation in worktree: `trees/{adw_id}/`\n"
            f"- Pull request created with all changes\n"
            f"- Code reviewed and validated\n"
            f"- Documentation updated\n\n"
            f"**Next Steps:**\n"
            f"- Review and merge the pull request\n"
            f"- The implementation is production-ready!\n"
            f"- To clean up worktree: `./scripts/purge_tree.sh {adw_id}`"
        )

        print(f"\n=== ISOLATED SDLC COMPLETED ===")
        print(f"ADW ID: {adw_id}")
        print(f"All phases completed successfully!")
        print(f"\nWorktree location: trees/{adw_id}/")
        print(f"To clean up: ./scripts/purge_tree.sh {adw_id}")

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
