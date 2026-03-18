"""Proximity agent — clusters hypotheses by semantic similarity."""
from __future__ import annotations

from darwin.state import ResearchState


def run(state: ResearchState) -> dict[str, object]:
    """Cluster hypotheses. Stub — to be implemented in da-7nx."""
    return {
        "proximity_clusters": [],
        "messages": [{"role": "agent", "agent": "proximity", "content": "stub"}],
    }
