#!/usr/bin/env python
"""
BROKEN VERSION: Parent process that reproduces the pipe buffer deadlock.

This mimics the problematic pattern in trigger_cron.py:
1. Uses subprocess.Popen with stdout=PIPE and stderr=PIPE
2. Doesn't read from pipes until process completes
3. Child process fills pipe buffer and blocks

Expected behavior: Will hang/deadlock when child output exceeds pipe buffer size.
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def main():
    print("=" * 80)
    print("BROKEN VERSION: Testing pipe buffer deadlock (should hang)")
    print("=" * 80)
    print()

    # Get path to child script
    script_dir = Path(__file__).parent
    child_script = script_dir / "test_pipe_deadlock_child.py"

    print(f"Starting child process: {child_script}")
    print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")
    print()

    start_time = time.time()

    # THIS IS THE BROKEN PATTERN (mimics trigger_cron.py line 266-272)
    print("Creating Popen with stdout=PIPE, stderr=PIPE...")
    process = subprocess.Popen(
        [sys.executable, str(child_script)],
        stdout=subprocess.PIPE,  # ← Creates pipe buffer (~64KB)
        stderr=subprocess.PIPE,  # ← Creates pipe buffer (~64KB)
        text=True,
    )

    print(f"Process started with PID: {process.pid}")
    print()
    print("⚠️  WARNING: Not reading from pipes until process completes...")
    print("⚠️  This will deadlock if child produces >64KB of output!")
    print()

    # Set a timeout to prevent hanging forever
    timeout = 30  # seconds
    print(f"Waiting for process to complete (timeout: {timeout}s)...")
    print()

    try:
        # THIS IS THE PROBLEM: We don't read pipes until communicate() is called
        # If child fills the pipe buffer, it will block and we'll block waiting for it
        stdout, stderr = process.communicate(timeout=timeout)

        elapsed = time.time() - start_time
        print()
        print("✅ Process completed!")
        print(f"End time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"Elapsed: {elapsed:.2f}s")
        print(f"Stdout length: {len(stdout)} bytes")
        print(f"Stderr length: {len(stderr)} bytes")
        print()
        print("First 200 chars of output:")
        print(stdout[:200])

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print()
        print("❌ DEADLOCK DETECTED!")
        print(f"Process hung for {elapsed:.2f}s and hit timeout")
        print(f"End time: {datetime.now().strftime('%H:%M:%S')}")
        print()
        print("The child process filled the pipe buffer and is blocked waiting")
        print("for the parent to read, but the parent won't read until the child")
        print("completes. This is a classic pipe buffer deadlock!")
        print()

        # Kill the process
        process.kill()
        process.wait()
        print(f"Killed process {process.pid}")

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
