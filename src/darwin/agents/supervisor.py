"""Supervisor agent — routes each iteration to generation, human_review, or END."""
from __future__ import annotations

from typing import Literal

from darwin.state import ResearchState


def run(state: ResearchState) -> dict[str, object]:
    """Increment iteration counter; decision is set by meta_review or human_review."""
    return {"iteration": state["iteration"] + 1}


def route(state: ResearchState) -> Literal["generate", "human_review", "end"]:
    """Conditional edge function: determines next node."""
    if state["iteration"] > state["max_iterations"]:
        return "end"
    decision = state.get("supervisor_decision", "continue")
    if decision == "stop":
        return "end"
    if decision == "human_review":
        return "human_review"
    return "generate"
