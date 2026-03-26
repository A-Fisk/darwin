"""Configuration constants and LLM endpoint configuration for darwin agents."""
from __future__ import annotations

import importlib.resources
import os
import tomllib
from typing import TypedDict

# Agent workflow configuration
TOP_N_HYPOTHESES: int = 3
NEW_PER_ITERATION: int = 5
EVOLVED_PER_ITERATION: int = 3
DEFAULT_MAX_ITERATIONS: int = 5
HUMAN_REVIEW_INTERVAL: int | None = None  # None = disabled unless meta_review triggers

# Token limits for LLM calls - tiered by task complexity
MAX_TOKENS_SIMPLE: int = 256      # Simple decisions, short responses
MAX_TOKENS_STANDARD: int = 512    # Standard responses, brief analysis
MAX_TOKENS_DETAILED: int = 1024   # Detailed comparisons, critiques
MAX_TOKENS_COMPLEX: int = 2048    # Complex analysis, rankings
MAX_TOKENS_CREATIVE: int = 4096   # Hypothesis generation, evolution


class LLMConfig(TypedDict, total=False):
    """Configuration for LLM client connections."""
    api_key: str | None
    auth_token: str | None
    base_url: str | None
    timeout: float | None
    max_retries: int | None
    model: str | None


def _load_config_from_file() -> dict[str, object]:
    """Load configuration from darwin.toml in user config or working directory."""
    # Try current working directory first
    cwd_config = "darwin.toml"
    if os.path.exists(cwd_config):
        with open(cwd_config, "rb") as f:
            return tomllib.load(f)

    # Try user config directory (~/.config/darwin/darwin.toml)
    config_dir = os.path.expanduser("~/.config/darwin")
    user_config = os.path.join(config_dir, "darwin.toml")
    if os.path.exists(user_config):
        with open(user_config, "rb") as f:
            return tomllib.load(f)

    return {}


def get_llm_config(
    api_key: str | None = None,
    auth_token: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    model: str | None = None,
) -> LLMConfig:
    """Get LLM configuration from CLI args, config files, and environment variables.

    Priority order (highest to lowest):
    1. Explicit function arguments (CLI flags)
    2. Environment variables
    3. Configuration files (./darwin.toml or ~/.config/darwin/darwin.toml)
    4. Defaults
    """
    config_data = _load_config_from_file()
    llm_section = config_data.get("llm", {})

    result: LLMConfig = {}

    # API key: CLI arg > env var > config file
    if api_key is not None:
        result["api_key"] = api_key
    elif "ANTHROPIC_API_KEY" in os.environ:
        result["api_key"] = os.environ["ANTHROPIC_API_KEY"]
    elif "api_key" in llm_section:
        result["api_key"] = str(llm_section["api_key"])

    # Auth token: CLI arg > env var > config file
    if auth_token is not None:
        result["auth_token"] = auth_token
    elif "ANTHROPIC_AUTH_TOKEN" in os.environ:
        result["auth_token"] = os.environ["ANTHROPIC_AUTH_TOKEN"]
    elif "auth_token" in llm_section:
        result["auth_token"] = str(llm_section["auth_token"])

    # Base URL: CLI arg > env var > config file
    if base_url is not None:
        result["base_url"] = base_url
    elif "ANTHROPIC_BASE_URL" in os.environ:
        result["base_url"] = os.environ["ANTHROPIC_BASE_URL"]
    elif "base_url" in llm_section:
        result["base_url"] = str(llm_section["base_url"])

    # Timeout: CLI arg > env var > config file > default
    if timeout is not None:
        result["timeout"] = timeout
    elif "DARWIN_TIMEOUT" in os.environ:
        result["timeout"] = float(os.environ["DARWIN_TIMEOUT"])
    elif "timeout" in llm_section:
        result["timeout"] = float(llm_section["timeout"])

    # Max retries: CLI arg > env var > config file > default (2)
    if max_retries is not None:
        result["max_retries"] = max_retries
    elif "DARWIN_MAX_RETRIES" in os.environ:
        result["max_retries"] = int(os.environ["DARWIN_MAX_RETRIES"])
    elif "max_retries" in llm_section:
        result["max_retries"] = int(llm_section["max_retries"])
    else:
        result["max_retries"] = 2  # Anthropic client default

    # Model: CLI arg > env var > config file > default
    if model is not None:
        result["model"] = model
    elif "DARWIN_MODEL" in os.environ:
        result["model"] = os.environ["DARWIN_MODEL"]
    elif "model" in llm_section:
        result["model"] = str(llm_section["model"])
    else:
        result["model"] = "claude-sonnet-4-6"  # Darwin default

    return result
