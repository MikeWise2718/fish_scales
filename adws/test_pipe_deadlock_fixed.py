#!/usr/bin/env python
"""
FIXED VERSION: Parent process that avoids pipe buffer deadlock.

This demonstrates the correct pattern:
1. Uses subprocess.Popen with stdout=PIPE and stderr=PIPE
2. Continuously reads from pipes using threads while process runs
3. Child process can write unlimited output without blocking

Expected behavior: Completes successfully without hanging.
"""

import subprocess
import sys
import time
import threading
import queue
from datetime import datetime
from pathlib import Path


def read_stream(stream, output_queue, stream_name):
    """
    Read from a stream and put lines into a queue.
    This runs in a separate thread to avoid blocking.
    """
    try:
        for line in stream:
            output_queue.put((stream_name, line))
    finally:
        output_queue.put((stream_name, None))  # Signal EOF


def main():
    print("=" * 80)
    print("FIXED VERSION: Continuous pipe reading (should complete successfully)")
    print("=" * 80)
    print()

    # Get path to child script
    script_dir = Path(__file__).parent
    child_script = script_dir / "test_pipe_deadlock_child.py"

    print(f"Starting child process: {child_script}")
    print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")
    print()

    start_time = time.time()

    # Create process with pipes
    print("Creating Popen with stdout=PIPE, stderr=PIPE...")
    process = subprocess.Popen(
        [sys.executable, str(child_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print(f"Process started with PID: {process.pid}")
    print()

    # THE FIX: Read pipes continuously using threads
    print("✅ Starting threads to read pipes continuously...")
    output_queue = queue.Queue()

    stdout_thread = threading.Thread(
        target=read_stream,
        args=(process.stdout, output_queue, 'stdout'),
        daemon=True
    )
    stderr_thread = threading.Thread(
        target=read_stream,
        args=(process.stderr, output_queue, 'stderr'),
        daemon=True
    )

    stdout_thread.start()
    stderr_thread.start()

    print("Threads started. Reading output...")
    print()

    # Collect output
    stdout_lines = []
    stderr_lines = []
    stdout_eof = False
    stderr_eof = False

    # Read from queue while process runs
    timeout = 30  # seconds
    poll_start = time.time()

    while True:
        # Drain the output queue
        try:
            while True:
                stream_name, line = output_queue.get_nowait()

                if line is None:
                    # EOF signal
                    if stream_name == 'stdout':
                        stdout_eof = True
                    else:
                        stderr_eof = True
                else:
                    # Store the line
                    if stream_name == 'stdout':
                        stdout_lines.append(line)
                    else:
                        stderr_lines.append(line)

        except queue.Empty:
            pass

        # Check if process completed
        returncode = process.poll()
        if returncode is not None:
            # Process finished, drain remaining output
            time.sleep(0.1)  # Give threads time to flush
            while not output_queue.empty():
                try:
                    stream_name, line = output_queue.get_nowait()
                    if line is not None:
                        if stream_name == 'stdout':
                            stdout_lines.append(line)
                        else:
                            stderr_lines.append(line)
                except queue.Empty:
                    break
            break

        # Check timeout
        if time.time() - poll_start > timeout:
            print()
            print(f"❌ Process exceeded timeout ({timeout}s)")
            process.kill()
            process.wait()
            return 1

        # Sleep briefly to avoid busy-waiting
        time.sleep(0.01)

    elapsed = time.time() - start_time

    # Wait for threads to complete
    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)

    # Print results
    print()
    print("✅ Process completed successfully!")
    print(f"End time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Return code: {returncode}")
    print(f"Stdout lines: {len(stdout_lines)}")
    print(f"Stderr lines: {len(stderr_lines)}")
    print()

    # Calculate total output size
    total_stdout_bytes = sum(len(line) for line in stdout_lines)
    print(f"Total stdout: ~{total_stdout_bytes:,} bytes")
    print()

    print("First 5 lines of output:")
    for line in stdout_lines[:5]:
        print(f"  {line.rstrip()}")

    print()
    print("Last 5 lines of output:")
    for line in stdout_lines[-5:]:
        print(f"  {line.rstrip()}")

    print()
    print("=" * 80)
    print("✅ SUCCESS: No deadlock occurred!")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
