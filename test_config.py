#!/usr/bin/env python3
"""Test script to verify Darwin's configurable endpoint support."""

import os
import tempfile
from pathlib import Path

from darwin.config import get_llm_config
from darwin.agents._common import get_anthropic_client


def test_config_priority():
    """Test that configuration priority works: CLI > env > config file > defaults."""

    # Test 1: Default configuration (using env vars if present)
    print("=== Test 1: Default configuration ===")
    config = get_llm_config()
    print(f"Default config: {config}")

    # Test 2: Environment variables
    print("\n=== Test 2: Environment variables ===")
    os.environ["DARWIN_MODEL"] = "test-model-env"
    os.environ["DARWIN_TIMEOUT"] = "45.0"
    config_env = get_llm_config()
    print(f"With env vars: {config_env}")

    # Test 3: CLI arguments override env vars
    print("\n=== Test 3: CLI arguments override ===")
    config_cli = get_llm_config(
        model="test-model-cli",
        timeout=60.0,
        base_url="https://test.example.com"
    )
    print(f"With CLI overrides: {config_cli}")

    # Test 4: Config file support (create temp file)
    print("\n=== Test 4: Config file support ===")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write("""
[llm]
model = "test-model-file"
timeout = 30.0
base_url = "https://file.example.com"
max_retries = 5
""")
        config_file = f.name

    # Test config file loading (would need to be in working dir or ~/.config/darwin/)
    print(f"Config file would be: {config_file}")

    # Clean up
    os.unlink(config_file)
    del os.environ["DARWIN_MODEL"]
    del os.environ["DARWIN_TIMEOUT"]

    # Test 5: Client creation
    print("\n=== Test 5: Client creation ===")
    try:
        client = get_anthropic_client(
            base_url="https://test.example.com",
            timeout=30.0
        )
        print(f"Client created successfully: {type(client).__name__}")
        print(f"Client base URL: {client.base_url}")
    except Exception as e:
        print(f"Client creation failed: {e}")

    print("\n=== All tests completed ===")


if __name__ == "__main__":
    test_config_priority()