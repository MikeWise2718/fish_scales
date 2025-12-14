#!/usr/bin/env python
"""
Test runner for pipe buffer deadlock reproduction.

Runs both the broken and fixed versions to demonstrate:
1. The broken version should timeout/hang (reproducing the bug)
2. The fixed version should complete successfully
"""

import subprocess
import sys
from pathlib import Path


def run_test(script_name, description):
    """Run a test script and return success/failure."""
    print()
    print("=" * 80)
    print(f"Running: {description}")
    print("=" * 80)

    script_path = Path(__file__).parent / script_name

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            timeout=60,  # Give it 60 seconds max
            capture_output=False,  # Let output go to terminal
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print()
        print(f"❌ {script_name} timed out after 60 seconds")
        return False
    except Exception as e:
        print()
        print(f"❌ {script_name} failed with exception: {e}")
        return False


def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "PIPE BUFFER DEADLOCK TEST SUITE" + " " * 31 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    print("This test suite demonstrates the pipe buffer deadlock issue that")
    print("caused 28-minute delays in ADW workflows.")
    print()

    results = {}

    # Test 1: Broken version (should timeout)
    print()
    print("TEST 1: Broken version (reproduces deadlock)")
    print("-" * 80)
    print("Expected: Should hang and timeout")
    print()
    input("Press Enter to run the broken version (will timeout in 30s)...")

    results['broken'] = run_test(
        "test_pipe_deadlock_broken.py",
        "Broken version (Popen with PIPE, no continuous reading)"
    )

    # Test 2: Fixed version (should succeed)
    print()
    print("TEST 2: Fixed version (continuous pipe reading)")
    print("-" * 80)
    print("Expected: Should complete successfully in <1 second")
    print()
    input("Press Enter to run the fixed version...")

    results['fixed'] = run_test(
        "test_pipe_deadlock_fixed.py",
        "Fixed version (continuous pipe reading with threads)"
    )

    # Summary
    print()
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 30 + "TEST SUMMARY" + " " * 36 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    # Broken version should fail (timeout)
    if not results['broken']:
        print("✅ Broken version: CORRECTLY TIMED OUT (bug reproduced)")
    else:
        print("⚠️  Broken version: Unexpectedly completed (bug not reproduced)")
        print("   This might happen if the child doesn't produce enough output")

    # Fixed version should succeed
    if results['fixed']:
        print("✅ Fixed version: SUCCESSFULLY COMPLETED (fix verified)")
    else:
        print("❌ Fixed version: FAILED (fix doesn't work)")

    print()

    if not results['broken'] and results['fixed']:
        print("=" * 80)
        print("✅ ALL TESTS PASSED!")
        print()
        print("The pipe buffer deadlock has been successfully:")
        print("  1. Reproduced (broken version timed out)")
        print("  2. Fixed (fixed version completed)")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print("⚠️  UNEXPECTED RESULTS - Review output above")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
