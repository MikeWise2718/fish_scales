#!/usr/bin/env python
"""
Test actual gh issue comment posting performance.

This will post real test comments to issue #14 to measure timing.
"""

import subprocess
import time
import os
import sys
from datetime import datetime

def test_comment_post(test_num, env_description, env):
    """Test posting a comment with specific environment."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    comment = f"[ADW-AGENTS] test_gh_comment_posting.py - Test #{test_num} at {timestamp}\nEnvironment: {env_description}"

    print(f"\n{'='*60}")
    print(f"Test #{test_num}: {env_description}")
    print(f"Comment: {comment[:100]}...")
    print(f"{'='*60}")

    # Get repo info
    repo_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True
    ).stdout.strip()
    repo_path = repo_url.replace("https://github.com/", "").replace(".git", "")

    cmd = [
        "gh", "issue", "comment", "14",
        "-R", repo_path,
        "--body", comment
    ]

    print(f"Starting at: {datetime.now().strftime('%H:%M:%S')}")
    start = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout
            env=env
        )
        duration = time.time() - start

        print(f"Finished at: {datetime.now().strftime('%H:%M:%S')}")
        print(f"Duration: {duration:.2f}s ({duration/60:.1f} minutes)")
        print(f"Return code: {result.returncode}")

        if result.returncode == 0:
            print(f"✅ SUCCESS - Comment posted")
            if result.stdout:
                print(f"Output: {result.stdout[:200]}")
        else:
            print(f"❌ FAILED")
            print(f"Error: {result.stderr}")

        return duration, result.returncode == 0

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        print(f"⏱️  TIMEOUT after {duration:.2f}s ({duration/60:.1f} minutes)")
        print("Command was killed due to timeout")
        return duration, False

    except Exception as e:
        duration = time.time() - start
        print(f"💥 Exception after {duration:.2f}s: {e}")
        return duration, False


def main():
    print("="*60)
    print("GitHub Issue Comment Posting Performance Test")
    print("="*60)
    print("\nThis will post REAL comments to issue #14")
    print("Press Ctrl+C within 5 seconds to cancel...")

    try:
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(0)

    print("\nProceeding with tests...\n")

    results = []

    # Test 1: env=None (inherit all)
    duration, success = test_comment_post(
        1,
        "env=None (inherits parent environment)",
        None
    )
    results.append(("Inherit parent", duration, success))

    # Test 2: ADW's safe environment
    from adw_modules.utils import get_safe_subprocess_env
    adw_env = get_safe_subprocess_env()

    duration, success = test_comment_post(
        2,
        "ADW get_safe_subprocess_env()",
        adw_env
    )
    results.append(("ADW safe env", duration, success))

    # Test 3: With GITHUB_PAT if available
    github_pat = os.getenv("GITHUB_PAT")
    if github_pat:
        token_env = {
            "GH_TOKEN": github_pat,
            "PATH": os.environ.get("PATH", ""),
        }
        duration, success = test_comment_post(
            3,
            "Minimal env with GH_TOKEN from GITHUB_PAT",
            token_env
        )
        results.append(("With GITHUB_PAT", duration, success))
    else:
        print("\n⚠️  GITHUB_PAT not set - skipping token test")
        print("Set GITHUB_PAT in .env to test token-based auth")

    # Summary
    print("\n" + "="*60)
    print("SUMMARY OF RESULTS")
    print("="*60)

    for env_name, duration, success in results:
        status = "✅ Success" if success else "❌ Failed"
        print(f"{env_name:20s}: {duration:6.2f}s ({duration/60:4.1f}m) - {status}")

    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)

    if results:
        avg_duration = sum(r[1] for r in results) / len(results)
        max_duration = max(r[1] for r in results)
        min_duration = min(r[1] for r in results)

        print(f"Average: {avg_duration:.2f}s ({avg_duration/60:.1f}m)")
        print(f"Minimum: {min_duration:.2f}s")
        print(f"Maximum: {max_duration:.2f}s ({max_duration/60:.1f}m)")

        if max_duration > 30:
            print("\n⚠️  WARNING: Detected slow comment posting (>30s)")
            print("This explains the 28-minute delays in ADW workflows!")
            print("\nPossible causes:")
            print("- Windows keyring access is slow")
            print("- GitHub API rate limiting")
            print("- Network issues")
            print("\nRecommended fixes:")
            print("1. Set GITHUB_PAT in .env to use token auth instead of keyring")
            print("2. Add timeout protection to all gh CLI calls")
            print("3. Add retry logic with exponential backoff")
        else:
            print("\n✅ All comment posts were fast (<30s)")
            print("The delay might be intermittent or specific to certain conditions")

    print("\nCheck issue #14 comments to verify all test comments were posted:")
    print("https://github.com/MikeWise2718/scipap/issues/14")


if __name__ == "__main__":
    main()
