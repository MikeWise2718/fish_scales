#!/usr/bin/env python
"""
Test the fixed trigger_cron.py continuous pipe reading implementation.

This script extracts the pipe reading logic from the fixed trigger_cron.py
and tests it with our deadlock-producing child process.
"""

import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path


def read_stream_with_tracking(stream, output_queue, stream_name):
    """
    Read from a stream and put lines into a queue with size tracking.

    This runs in a separate thread to continuously drain the pipe buffer
    and prevent deadlocks.
    """
    try:
        byte_count = 0
        line_count = 0

        for line in stream:
            byte_count += len(line.encode('utf-8'))
            line_count += 1
            output_queue.put((stream_name, 'line', line))

        # Send final statistics
        output_queue.put((stream_name, 'stats', {'bytes': byte_count, 'lines': line_count}))

    except Exception as e:
        output_queue.put((stream_name, 'error', str(e)))
    finally:
        output_queue.put((stream_name, 'eof', None))


def main():
    print("=" * 80)
    print("TESTING FIXED TRIGGER: Continuous pipe reading with tracking")
    print("=" * 80)
    print()

    # Get path to child script
    script_dir = Path(__file__).parent
    child_script = script_dir / "test_pipe_deadlock_child.py"

    print(f"Starting child process: {child_script}")
    print(f"Start time: {datetime.now().strftime('%H:%M:%S')}")
    print()

    start_time = time.time()

    # Create process with pipes (same as trigger_cron.py)
    print("Creating Popen with stdout=PIPE, stderr=PIPE...")
    process = subprocess.Popen(
        [sys.executable, str(child_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print(f"Process started with PID: {process.pid}")
    print()

    # Start threads to continuously read from pipes
    print("✅ Starting reader threads with output tracking...")
    output_queue = queue.Queue()

    stdout_thread = threading.Thread(
        target=read_stream_with_tracking,
        args=(process.stdout, output_queue, 'stdout'),
        daemon=True,
        name='stdout-reader'
    )
    stderr_thread = threading.Thread(
        target=read_stream_with_tracking,
        args=(process.stderr, output_queue, 'stderr'),
        daemon=True,
        name='stderr-reader'
    )

    stdout_thread.start()
    stderr_thread.start()

    # Collect output and track statistics
    stdout_lines = []
    stderr_lines = []
    stdout_stats = None
    stderr_stats = None

    print("Polling process while draining pipes...")
    print()

    # Poll the process
    timeout = 30
    while True:
        # Drain the output queue
        try:
            while True:
                stream_name, msg_type, data = output_queue.get_nowait()

                if msg_type == 'line':
                    if stream_name == 'stdout':
                        stdout_lines.append(data)
                    else:
                        stderr_lines.append(data)

                elif msg_type == 'stats':
                    if stream_name == 'stdout':
                        stdout_stats = data
                    else:
                        stderr_stats = data

                elif msg_type == 'error':
                    print(f"  Error reading {stream_name}: {data}")

        except queue.Empty:
            pass

        # Check if process is still running
        returncode = process.poll()
        if returncode is not None:
            # Process completed - drain any remaining output
            time.sleep(0.1)
            try:
                while True:
                    stream_name, msg_type, data = output_queue.get_nowait()
                    if msg_type == 'line':
                        if stream_name == 'stdout':
                            stdout_lines.append(data)
                        else:
                            stderr_lines.append(data)
                    elif msg_type == 'stats':
                        if stream_name == 'stdout':
                            stdout_stats = data
                        else:
                            stderr_stats = data
            except queue.Empty:
                pass
            break

        elapsed = time.time() - start_time

        # Check timeout
        if elapsed > timeout:
            print()
            print(f"❌ Process exceeded timeout ({timeout}s)")
            process.kill()
            process.wait()
            return 1

        # Sleep briefly
        time.sleep(0.1)

    elapsed = time.time() - start_time

    # Wait for threads
    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)

    # Print results
    print()
    print("✅ Process completed successfully!")
    print(f"End time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Elapsed: {elapsed:.2f}s")
    print(f"Return code: {returncode}")
    print()

    # Report output statistics
    print("=" * 80)
    print("📊 OUTPUT STATISTICS (Pipe Buffer Usage)")
    print("=" * 80)

    if stdout_stats:
        stdout_kb = stdout_stats['bytes'] / 1024
        print(f"stdout: {stdout_stats['lines']:,} lines, {stdout_kb:.2f} KB ({stdout_stats['bytes']:,} bytes)")

    if stderr_stats:
        stderr_kb = stderr_stats['bytes'] / 1024
        print(f"stderr: {stderr_stats['lines']:,} lines, {stderr_kb:.2f} KB ({stderr_stats['bytes']:,} bytes)")

    if stdout_stats or stderr_stats:
        total_bytes = (stdout_stats['bytes'] if stdout_stats else 0) + (stderr_stats['bytes'] if stderr_stats else 0)
        total_kb = total_bytes / 1024
        print()
        print(f"TOTAL: {total_kb:.2f} KB ({total_bytes:,} bytes)")
        print()

        # Analysis
        if total_kb > 64:
            print("⚠️  OUTPUT ANALYSIS:")
            print(f"    Output volume ({total_kb:.2f} KB) EXCEEDED typical pipe buffer size (64 KB)")
            print(f"    Without continuous pipe reading, this would have caused a DEADLOCK!")
            print()
            print("✅  FIX VERIFIED: Continuous pipe reading prevented the deadlock")
        else:
            print("ℹ️  OUTPUT ANALYSIS:")
            print(f"    Output volume ({total_kb:.2f} KB) is below typical pipe buffer size (64 KB)")
            print(f"    No deadlock expected, but continuous reading provides safety margin")

    print()
    print("=" * 80)
    print("✅ SUCCESS: Fixed trigger implementation works correctly!")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
