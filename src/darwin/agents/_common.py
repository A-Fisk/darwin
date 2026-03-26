"""Shared utilities for darwin agent nodes."""
from __future__ import annotations

import importlib.resources
import json
import re
import tomllib
from typing import NamedTuple, Any

import anthropic

from darwin.state import Hypothesis


def get_anthropic_client(
    api_key: str | None = None,
    auth_token: str | None = None,
    base_url: str | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
) -> anthropic.Anthropic:
    """Create an Anthropic client with the given configuration.

    Uses darwin.config.get_llm_config() to resolve configuration from CLI args,
    environment variables, and config files.
    """
    from darwin.config import get_llm_config

    # Merge CLI args if they haven't been explicitly overridden
    try:
        from darwin.cli import get_cli_llm_args
        cli_args = get_cli_llm_args()

        # Use CLI args as defaults if not explicitly provided to this function
        if api_key is None:
            api_key = cli_args.get("api_key")
        if auth_token is None:
            auth_token = cli_args.get("auth_token")
        if base_url is None:
            base_url = cli_args.get("base_url")
        if timeout is None:
            timeout = cli_args.get("timeout")
        if max_retries is None:
            max_retries = cli_args.get("max_retries")
    except ImportError:
        # CLI module not available (e.g., when used as a library)
        pass

    config = get_llm_config(
        api_key=api_key,
        auth_token=auth_token,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
    )

    # Create client with resolved config (None values are filtered out)
    client_kwargs: dict[str, Any] = {k: v for k, v in config.items() if v is not None and k != "model"}

    return anthropic.Anthropic(**client_kwargs)


def get_default_model() -> str:
    """Get the default model from configuration."""
    from darwin.config import get_llm_config

    # Try to get model from CLI args first
    try:
        from darwin.cli import get_cli_llm_args
        cli_args = get_cli_llm_args()
        cli_model = cli_args.get("model")
        if cli_model:
            return cli_model
    except ImportError:
        pass

    config = get_llm_config()
    return config["model"] or "claude-sonnet-4-6"


def parse_json_response(
    message: anthropic.types.Message, prefill: str = ""
) -> object:
    """Extract and parse a JSON response from a Claude API message.

    Handles the case where the model wraps output in markdown fences despite
    instructions not to, and raises a clear error when the response is empty.

    If `prefill` is provided, it is prepended to the response text before
    parsing — use this when the assistant turn was prefilled (e.g. "{") to
    force JSON output without preamble.
    """
    if not message.content:
        raise ValueError("Claude API returned empty content list")

    block = message.content[0]
    if block.type != "text":
        raise ValueError(f"Expected text content block, got {block.type!r}")

    text = (prefill + block.text).strip()
    if not text:
        raise ValueError("Claude API returned an empty text response")

    # Strip markdown fences (```json ... ``` or ``` ... ```) if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    if message.stop_reason == "max_tokens":
        raise ValueError(
            f"Claude API response was truncated (stop_reason='max_tokens'). "
            f"Response length: {len(text)} chars. Increase max_tokens for this agent."
        )

    # Handle cases where LLM response contains valid JSON followed by additional text
    # json.loads() would raise "Extra data" error, so use JSONDecoder to parse first valid JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        if "Extra data" in str(e):
            # Try to parse just the first valid JSON object
            decoder = json.JSONDecoder()
            try:
                obj, idx = decoder.raw_decode(text)
                return obj
            except json.JSONDecodeError:
                # If raw_decode also fails, re-raise the original error
                raise e
        else:
            # Re-raise other JSON errors (malformed JSON, etc.)
            raise


def latest_hypotheses(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    """Return the most recent version of each hypothesis by ID.

    Since the state reducer for `hypotheses` uses operator.add (append-only),
    agents that update existing hypotheses append updated copies. This function
    deduplicates by ID, returning the last-seen version of each.
    """
    seen: dict[str, Hypothesis] = {}
    for h in hypotheses:
        seen[h["id"]] = h
    return list(seen.values())


class Criterion(NamedTuple):
    name: str
    description: str
    weight: float


_criteria_cache: list[Criterion] | None = None


def load_criteria() -> list[Criterion]:
    """Load evaluation criteria from criteria.toml (cached after first load)."""
    global _criteria_cache
    if _criteria_cache is not None:
        return _criteria_cache

    data = importlib.resources.files("darwin").joinpath("criteria.toml").read_bytes()
    config = tomllib.loads(data.decode())
    _criteria_cache = [
        Criterion(
            name=c["name"],
            description=c["description"],
            weight=float(c.get("weight", 1.0)),
        )
        for c in config.get("criteria", [])
    ]
    return _criteria_cache


def criteria_prompt_block() -> str:
    """Return a formatted criteria list suitable for embedding in prompts."""
    criteria = load_criteria()
    lines = []
    for c in criteria:
        lines.append(f"- {c.name} (weight {c.weight}): {c.description}")
    return "\n".join(lines)
