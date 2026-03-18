"""Shared utilities for darwin agent nodes."""
from __future__ import annotations

from darwin.state import Hypothesis


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
