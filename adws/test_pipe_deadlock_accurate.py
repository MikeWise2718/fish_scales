#!/usr/bin/env python
"""
ACCURATE REPRODUCTION: Mimics the exact pattern used in trigger_cron.py

This reproduces the actual code pattern:
1. subprocess.Popen with stdout=PIPE, stderr=PIPE
2. Poll loop that checks process.poll() without reading pipes
3. After loop exits, call process.communicate(timeout=10)

The deadlock can occur if:
- Child produces output continuously during polling
- Output exceeds buffer size while we're in the polling loop
- Child blocks on write, never completes
- We never exit polling loop because process.poll() returns None
- DEADLOCK
"""

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def main():
    print("=" * 80)
    print("ACCURATE REPRODUCTION: Mimics trigger_cron.py pattern")
    print("=" * 80)
    print()

    # Get path to child script
    script_dir = Path(__file__).parent
    child_script = script_dir / "test_pipe_deadlock_child.py"

    print(f"Starting child process: {child_script}")
    print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")
    print()

    start_time = time.time()

    # THIS MIMICS trigger_cron.py (line 266-273)
    print("Creating Popen with stdout=PIPE, stderr=PIPE (like trigger_cron.py)...")
    process = subprocess.Popen(
        [sys.executable, str(child_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print(f"Process started with PID: {process.pid}")
    print()

    # THIS MIMICS trigger_cron.py polling loop (line 281-319)
    print("Entering polling loop (like trigger_cron.py)...")
    print("⚠️  NOT reading from pipes during polling...")
    print()

    timeout = 30
    check_interval = 0.5

    while True:
        # Check if process is still running (line 283-286)
        returncode = process.poll()
        if returncode is not None:
            print(f"Process completed with returncode: {returncode}")
            break

        elapsed = time.time() - start_time

        # Check timeout (line 311-316)
        if elapsed > timeout:
            print()
            print(f"❌ TIMEOUT: Process exceeded {timeout}s")
            print()
            print("This might indicate a deadlock:")
            print("- Child is blocked writing to full pipe buffer")
            print("- Parent is waiting in poll loop, not reading pipes")
            print("- Classic deadlock scenario")
            process.kill()
            process.wait()
            return 1

        # Sleep briefly (line 319)
        time.sleep(check_interval)

        # Show we're still polling
        if int(elapsed) % 5 == 0 and elapsed > 0:
            print(f"  ...still polling after {int(elapsed)}s")

    # THIS MIMICS trigger_cron.py line 322
    print()
    print("Exited polling loop. Calling communicate(timeout=10)...")
    print()

    try:
        stdout, stderr = process.communicate(timeout=10)

        elapsed = time.time() - start_time
        print("✅ communicate() completed successfully!")
        print(f"Elapsed time: {elapsed:.2f}s")
        print(f"Stdout length: {len(stdout):,} bytes")
        print(f"Stderr length: {len(stderr):,} bytes")
        print()
        print("First 200 chars:")
        print(stdout[:200])
        return 0

    except subprocess.TimeoutExpired:
        print()
        print("❌ communicate() TIMED OUT!")
        print()
        print("This can happen if there's too much buffered output to read in 10s")
        process.kill()
        process.wait()
        return 1


if __name__ == "__main__":
    sys.exit(main())
