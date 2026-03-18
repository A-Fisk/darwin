"""Human-review node — interrupt for human feedback."""
from __future__ import annotations

from langgraph.types import interrupt

from darwin.state import ResearchState


def run(state: ResearchState) -> dict[str, object]:
    """Pause graph for human feedback via LangGraph interrupt."""
    feedback: object = interrupt(
        {
            "top_hypotheses": state["top_hypotheses"],
            "meta_review_notes": state["meta_review_notes"],
            "iteration": state["iteration"],
        }
    )
    decision = "stop" if str(feedback).strip().lower() == "stop" else "continue"
    return {
        "human_feedback": str(feedback),
        "supervisor_decision": decision,
        "messages": [{"role": "human", "content": str(feedback)}],
    }
