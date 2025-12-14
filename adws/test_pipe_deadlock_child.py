#!/usr/bin/env python
"""
Child process that generates lots of output to stdout.
This simulates ADW workflow scripts that print progress messages.

The output volume is designed to exceed typical pipe buffer sizes (~64KB on Windows).
"""

import sys
import time


def main():
    # Print a startup message
    print("Child process starting...", flush=True)

    # Simulate the kind of output ADW workflows produce
    # Each line is ~100 bytes, so we need enough to exceed Windows pipe buffer
    # Windows pipes can be 4KB-1MB depending on configuration
    # Let's generate 2MB to be sure (20,000 lines)

    for i in range(20000):
        # Simulate various types of messages
        if i % 10 == 0:
            msg = f"[{i:04d}] Processing step {i}: Analyzing codebase and generating implementation plan..."
        elif i % 10 == 5:
            msg = f"[{i:04d}] Successfully posted comment to issue #123 - workflow progressing normally"
        else:
            msg = f"[{i:04d}] INFO - Executing git operations in worktree at path /some/long/path/trees/abc123"

        print(msg)

        # Don't flush - this is key to reproducing the issue
        # In real code, print() buffers output which goes to the pipe

        # Simulate some work
        if i % 100 == 0:
            time.sleep(0.01)  # Small delay every 100 iterations

    print("Child process completed successfully!", flush=True)
    print(f"Total output: ~{20000 * 100} bytes", flush=True)

    # Exit successfully
    sys.exit(0)


if __name__ == "__main__":
    main()
