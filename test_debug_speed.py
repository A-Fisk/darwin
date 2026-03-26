#!/usr/bin/env python3
"""Quick test script to demonstrate debug mode speed differences."""

import subprocess
import time
import sys


def time_command(cmd, description):
    """Time a command execution."""
    print(f"\n🚀 Testing: {description}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)

    start_time = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        end_time = time.time()
        duration = end_time - start_time

        if result.returncode == 0:
            print(f"✅ Completed in {duration:.1f} seconds")
            return duration
        else:
            print(f"❌ Failed (exit code {result.returncode})")
            print("STDERR:", result.stderr)
            return None
    except subprocess.TimeoutExpired:
        print(f"⏰ Timed out after 3 minutes")
        return None
    except Exception as e:
        print(f"💥 Error: {e}")
        return None


def main():
    """Run speed comparison tests."""
    print("🧬 Darwin Debug Mode Speed Test")
    print("=" * 50)

    base_cmd = [
        "uv", "run", "python", "-m", "darwin",
        "What are the key factors in bacterial evolution?",
        "--iterations", "1"
    ]

    tests = [
        (base_cmd + ["--debug", "mock"], "Mock Mode (no LLM calls)"),
        (base_cmd + ["--debug", "fast"], "Fast Mode (reduced LLM calls)"),
        (base_cmd + ["--debug", "minimal"], "Minimal Mode (core LLMs only)"),
    ]

    # Only test full mode if explicitly requested (it's slow)
    if "--include-full" in sys.argv:
        tests.append((base_cmd + ["--debug", "off"], "Full Mode (all LLM calls)"))

    results = {}

    for cmd, description in tests:
        duration = time_command(cmd, description)
        if duration is not None:
            results[description] = duration

    print("\n" + "=" * 50)
    print("📊 RESULTS SUMMARY")
    print("=" * 50)

    for description, duration in results.items():
        print(f"{description:30} {duration:6.1f}s")

    if len(results) > 1:
        fastest = min(results.values())
        print(f"\nSpeed improvements over full mode:")
        for description, duration in results.items():
            if duration > fastest:
                speedup = duration / fastest
                print(f"  {description:28} {speedup:.1f}x slower")
            else:
                print(f"  {description:28} baseline (fastest)")


if __name__ == "__main__":
    main()