#!/usr/bin/env python
"""
Test GitHub CLI (gh) performance and authentication.

This script times various gh operations to identify bottlenecks.
"""

import subprocess
import time
import sys
import os
from pathlib import Path

def time_command(description, cmd, env=None):
    """Time a command and return duration and success status."""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,  # 1 minute timeout
            env=env
        )
        duration = time.time() - start

        print(f"Duration: {duration:.2f}s")
        print(f"Return code: {result.returncode}")

        if result.returncode == 0:
            print(f"✅ Success")
            if len(result.stdout) < 500:
                print(f"Output: {result.stdout[:500]}")
            else:
                print(f"Output (truncated): {result.stdout[:500]}...")
        else:
            print(f"❌ Failed")
            print(f"Error: {result.stderr}")

        return duration, result.returncode == 0

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        print(f"⏱️  TIMEOUT after {duration:.2f}s")
        return duration, False
    except Exception as e:
        duration = time.time() - start
        print(f"💥 Exception: {e}")
        return duration, False


def get_github_env():
    """Get environment with GitHub token if available."""
    github_pat = os.getenv("GITHUB_PAT")
    if not github_pat:
        return None

    env = {
        "GH_TOKEN": github_pat,
        "PATH": os.environ.get("PATH", ""),
    }
    return env


def main():
    print("GitHub CLI Performance Test")
    print("=" * 60)

    # Test 1: Check gh installation
    time_command(
        "gh version",
        ["gh", "version"],
        None
    )

    # Test 2: Check authentication status
    time_command(
        "gh auth status",
        ["gh", "auth", "status"],
        None
    )

    # Test 3: Check auth with GITHUB_PAT
    env = get_github_env()
    if env:
        print("\n📝 GITHUB_PAT is set")
        time_command(
            "gh auth status (with GITHUB_PAT)",
            ["gh", "auth", "status"],
            env
        )
    else:
        print("\n⚠️  GITHUB_PAT is not set")

    # Test 4: Simple API call - list repos
    time_command(
        "gh repo list (limit 1)",
        ["gh", "repo", "list", "--limit", "1"],
        env
    )

    # Test 5: Get repo from git remote
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True
        )
        repo_url = result.stdout.strip()
        repo_path = repo_url.replace("https://github.com/", "").replace(".git", "")
        print(f"\n📍 Repository: {repo_path}")

        # Test 6: View issue #14
        time_command(
            "gh issue view 14",
            ["gh", "issue", "view", "14", "-R", repo_path, "--json", "number,title"],
            env
        )

        # Test 7: List issues (limit 1)
        time_command(
            "gh issue list (limit 1)",
            ["gh", "issue", "list", "-R", repo_path, "--limit", "1"],
            env
        )

        # Test 8: Post a test comment (DRY RUN - we'll just show what would be posted)
        test_comment = "[ADW-AGENTS] test_gh_performance.py diagnostic test"
        print(f"\n{'='*60}")
        print(f"Testing: POST comment (simulation)")
        print(f"Would post: {test_comment}")
        print(f"{'='*60}")
        print("⚠️  Skipping actual comment post to avoid spam")
        print("To test comment posting, uncomment the code below")

        # Uncomment to actually test comment posting:
        # time_command(
        #     "gh issue comment 14 (TEST)",
        #     ["gh", "issue", "comment", "14", "-R", repo_path, "--body", test_comment],
        #     env
        # )

    except Exception as e:
        print(f"\n❌ Could not get repo info: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("\nIf you see slow operations (>5s), possible causes:")
    print("1. GitHub API rate limiting")
    print("2. Network latency")
    print("3. gh CLI authentication issues")
    print("4. Large repository data")
    print("\nRecommendations:")
    print("- Ensure GITHUB_PAT is set in .env")
    print("- Check 'gh auth status' shows correct account")
    print("- Consider caching gh responses when possible")
    print("- Add timeouts to all gh CLI calls")


if __name__ == "__main__":
    main()
