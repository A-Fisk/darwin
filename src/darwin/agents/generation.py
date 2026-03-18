"""Generation agent — produces new hypotheses each iteration."""
from __future__ import annotations

from darwin.state import Hypothesis, ResearchState


def run(state: ResearchState) -> dict[str, object]:
    """Generate new hypotheses. Stub — to be implemented in da-t2q."""
    return {
        "hypotheses": [],
        "messages": [{"role": "agent", "agent": "generation", "content": "stub"}],
    }
