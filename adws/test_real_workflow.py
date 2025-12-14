#!/usr/bin/env python
"""
Test the fixed trigger_cron.py with a real workflow execution.

This script triggers a real ADW workflow (adw_plan_iso) for issue #17
and captures the output statistics to verify the fix works in production.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the trigger function
from adws.adw_triggers.trigger_cron import trigger_adw_workflow

def main():
    print("=" * 80)
    print("TESTING FIXED TRIGGER WITH REAL WORKFLOW")
    print("=" * 80)
    print()

    issue_number = 17
    workflow = "adw_plan_iso"  # Planning only - quick execution
    timeout = 600  # 10 minutes should be plenty for planning

    print(f"Issue: #{issue_number}")
    print(f"Workflow: {workflow}")
    print(f"Timeout: {timeout}s ({timeout//60} minutes)")
    print()
    print("Starting workflow execution...")
    print("This will test:")
    print("  - Continuous pipe reading")
    print("  - Output tracking")
    print("  - Statistics reporting")
    print()
    print("-" * 80)
    print()

    try:
        success = trigger_adw_workflow(
            issue_number=issue_number,
            workflow=workflow,
            timeout=timeout
        )

        print()
        print("-" * 80)
        print()

        if success:
            print("✅ WORKFLOW COMPLETED SUCCESSFULLY!")
            print()
            print("The output above should show:")
            print("  - 📊 Output Statistics (Pipe Buffer Usage)")
            print("  - stdout/stderr line counts and byte counts")
            print("  - Warning if output exceeded 64KB")
            print()
            return 0
        else:
            print("❌ WORKFLOW FAILED")
            print()
            print("Check the output above for error details.")
            print()
            return 1

    except Exception as e:
        print()
        print(f"❌ EXCEPTION: {e}")
        print()
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
