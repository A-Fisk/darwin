"""Shared utilities for darwin agent nodes."""
from __future__ import annotations

import json
import re

import anthropic

from darwin.state import Hypothesis


def parse_json_response(message: anthropic.types.Message) -> object:
    """Extract and parse a JSON response from a Claude API message.

    Handles the case where the model wraps output in markdown fences despite
    instructions not to, and raises a clear error when the response is empty.
    """
    if not message.content:
        raise ValueError("Claude API returned empty content list")

    block = message.content[0]
    if block.type != "text":
        raise ValueError(f"Expected text content block, got {block.type!r}")

    text = block.text.strip()
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

    return json.loads(text)


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
