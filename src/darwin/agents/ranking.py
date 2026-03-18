"""Ranking agent — sorts hypotheses; populates ranked_ids / top_hypotheses."""
from __future__ import annotations

from darwin.state import ResearchState


def run(state: ResearchState) -> dict[str, object]:
    """Rank hypotheses. Stub — to be implemented in da-7nx."""
    return {
        "ranked_ids": [],
        "top_hypotheses": [],
        "messages": [{"role": "agent", "agent": "ranking", "content": "stub"}],
    }
