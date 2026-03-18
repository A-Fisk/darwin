"""Reflection agent — critiques and scores each hypothesis."""
from __future__ import annotations

from darwin.state import ResearchState


def run(state: ResearchState) -> dict[str, object]:
    """Reflect on hypotheses. Stub — to be implemented in da-7nx."""
    return {
        "messages": [{"role": "agent", "agent": "reflection", "content": "stub"}],
    }
