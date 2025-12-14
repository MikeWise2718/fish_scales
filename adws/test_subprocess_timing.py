#!/usr/bin/env python
"""
Test to see if there's a delay AFTER subprocess.run() completes.

This will help us understand if the 28-minute delay is:
A) During the gh command execution
B) After the gh command returns but before Python continues
"""

import subprocess
import time
from datetime import datetime

def main():
    print("Testing subprocess.run() timing")
    print("="*60)

    # Test posting a comment
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    comment = f"[ADW-AGENTS] test_subprocess_timing.py at {timestamp}"

    cmd = [
        "gh", "issue", "comment", "14",
        "-R", "MikeWise2718/scipap",
        "--body", comment
    ]

    print(f"\n1. Before subprocess.run(): {datetime.now().strftime('%H:%M:%S.%f')}")
    start = time.time()

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30
    )

    after_run = time.time()
    print(f"2. After subprocess.run(): {datetime.now().strftime('%H:%M:%S.%f')}")
    print(f"   Duration: {after_run - start:.4f}s")
    print(f"   Return code: {result.returncode}")

    # Do some trivial work
    x = 0
    for i in range(1000):
        x += i

    after_work = time.time()
    print(f"3. After trivial work: {datetime.now().strftime('%H:%M:%S.%f')}")
    print(f"   Duration: {after_work - after_run:.4f}s")

    # Try to access result.stdout
    print(f"4. Accessing result.stdout: {datetime.now().strftime('%H:%M:%S.%f')}")
    stdout_len = len(result.stdout) if result.stdout else 0
    print(f"   Stdout length: {stdout_len}")

    after_stdout = time.time()
    print(f"5. After stdout access: {datetime.now().strftime('%H:%M:%S.%f')}")
    print(f"   Duration: {after_stdout - after_work:.4f}s")

    print(f"\nTotal time: {after_stdout - start:.4f}s")

    print("\n" + "="*60)
    print("If you see a large gap between any steps, that's where")
    print("the delay occurs.")


if __name__ == "__main__":
    main()
