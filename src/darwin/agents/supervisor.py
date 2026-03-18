"""Supervisor agent — routes each iteration to generation, human_review, or END."""
from __future__ import annotations

import json
from typing import Literal

import anthropic

from darwin.agents._common import latest_hypotheses
from darwin.config import TOP_N_HYPOTHESES
from darwin.state import ResearchState

_SYSTEM = """\
You are a research supervisor orchestrating a multi-iteration hypothesis search.
Given the current research state, decide whether to continue generating hypotheses,
request human review, or stop.

Output a JSON object with one key:
  "decision": one of "continue", "stop", or "human_review"

Guidelines:
  "continue"     — default; keep iterating to improve hypotheses
  "stop"         — the hypotheses are excellent and further iteration is unlikely to help
  "human_review" — progress has stalled or a significant decision needs human input

Output ONLY valid JSON — no prose, no markdown fences."""


def run(state: ResearchState) -> dict[str, object]:
    """Increment iteration and optionally refine supervisor_decision via LLM."""
    new_iteration = state["iteration"] + 1

    # On the very first iteration there's nothing to review — just start generating
    if state["iteration"] == 0:
        return {
            "iteration": new_iteration,
            "messages": [
                {
                    "role": "agent",
                    "agent": "supervisor",
                    "content": "iteration 0 → starting generation",
                }
            ],
        }

    client = anthropic.Anthropic()
    pool = latest_hypotheses(state["hypotheses"])
    top = state.get("top_hypotheses") or pool[:TOP_N_HYPOTHESES]
    top_text = "\n".join(f'[score={h["score"]:.2f}] {h["text"]}' for h in top)

    prior_decision = state.get("supervisor_decision", "continue")
    prompt = (
        f"Topic: {state['topic']}\n"
        f"Iteration just completed: {state['iteration']} of {state['max_iterations']}\n"
        f"Meta-review notes: {state.get('meta_review_notes', 'n/a')}\n"
        f"Prior decision: {prior_decision}\n\n"
        f"Top hypotheses:\n{top_text}"
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=64,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    result: dict[str, str] = json.loads(message.content[0].text)
    decision = result.get("decision", prior_decision)
    if decision not in ("continue", "stop", "human_review"):
        decision = prior_decision

    return {
        "iteration": new_iteration,
        "supervisor_decision": decision,
        "messages": [
            {
                "role": "agent",
                "agent": "supervisor",
                "content": f"iteration {new_iteration}; decision={decision}",
            }
        ],
    }


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
