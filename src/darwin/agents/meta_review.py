"""Meta-review agent — cross-iteration quality audit."""
from __future__ import annotations

from darwin.state import ResearchState


def run(state: ResearchState) -> dict[str, object]:
    """Audit quality across iterations. Stub — to be implemented in da-7nx."""
    return {
        "supervisor_decision": "continue",
        "meta_review_notes": "",
        "messages": [{"role": "agent", "agent": "meta_review", "content": "stub"}],
    }
