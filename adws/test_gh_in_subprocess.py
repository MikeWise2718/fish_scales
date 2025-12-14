#!/usr/bin/env python
"""
Test gh CLI behavior when called from subprocess with minimal environment.

This simulates what happens in ADW workflows.
"""

import subprocess
import time
import os

def test_gh_with_env(env_description, env):
    """Test gh command with specific environment."""
    print(f"\n{'='*60}")
    print(f"Test: {env_description}")
    print(f"Environment: {env}")
    print(f"{'='*60}")

    cmd = ["gh", "auth", "status"]

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )
        duration = time.time() - start

        print(f"Duration: {duration:.2f}s")
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout[:200]}")
        if result.stderr:
            print(f"Stderr: {result.stderr[:200]}")

    except subprocess.TimeoutExpired:
        duration = time.time() - start
        print(f"⏱️  TIMEOUT after {duration:.2f}s")
    except Exception as e:
        duration = time.time() - start
        print(f"💥 Exception after {duration:.2f}s: {e}")


def main():
    print("Testing gh CLI in different subprocess environments")
    print("=" * 60)

    # Test 1: None (inherits all)
    test_gh_with_env(
        "env=None (inherits parent environment)",
        None
    )

    # Test 2: Minimal env (PATH only)
    test_gh_with_env(
        "Minimal env (PATH only)",
        {"PATH": os.environ.get("PATH", "")}
    )

    # Test 3: With GITHUB_PAT if available
    github_pat = os.getenv("GITHUB_PAT")
    if github_pat:
        test_gh_with_env(
            "With GH_TOKEN from GITHUB_PAT",
            {
                "GH_TOKEN": github_pat,
                "PATH": os.environ.get("PATH", ""),
            }
        )
    else:
        print("\n⚠️  GITHUB_PAT not set, skipping token test")

    # Test 4: What ADW actually uses (from utils.get_safe_subprocess_env)
    print(f"\n{'='*60}")
    print("Test: ADW's get_safe_subprocess_env()")
    print(f"{'='*60}")

    from adw_modules.utils import get_safe_subprocess_env
    adw_env = get_safe_subprocess_env()

    print(f"Environment variables in ADW env:")
    for key in sorted(adw_env.keys()):
        if key in ["PATH", "ANTHROPIC_API_KEY", "GITHUB_PAT", "GH_TOKEN"]:
            value = adw_env[key]
            if value:
                if key in ["ANTHROPIC_API_KEY", "GITHUB_PAT", "GH_TOKEN"]:
                    print(f"  {key}: {'*' * 20} (set, length={len(value)})")
                else:
                    print(f"  {key}: {value[:50]}...")
            else:
                print(f"  {key}: None")

    test_gh_with_env(
        "ADW get_safe_subprocess_env()",
        adw_env
    )

    # Test 5: Test actual gh issue comment
    print(f"\n{'='*60}")
    print("Test: gh issue comment (timing only, no actual post)")
    print(f"{'='*60}")

    repo_url = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True
    ).stdout.strip()
    repo_path = repo_url.replace("https://github.com/", "").replace(".git", "")

    cmd = [
        "gh", "issue", "view", "14",
        "-R", repo_path,
        "--json", "number,title"
    ]

    print(f"Command: {' '.join(cmd)}")
    start = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True, env=adw_env, timeout=30)
    duration = time.time() - start
    print(f"Duration: {duration:.2f}s")
    print(f"Success: {result.returncode == 0}")


if __name__ == "__main__":
    main()
