"""Reflection agent — critiques and scores each hypothesis."""
from __future__ import annotations

import json

import anthropic

from darwin.agents._common import latest_hypotheses
from darwin.state import Hypothesis, ResearchState

_SYSTEM = """\
You are a rigorous scientific critic evaluating research hypotheses.
Given a topic and a hypothesis, critique its scientific merit.

Output a JSON object with exactly two keys:
  "critique": a concise critique (1-3 sentences)
  "score": a float 0.0–1.0 (1.0 = excellent: novel, testable, specific; 0.0 = poor)

Output ONLY valid JSON — no prose, no markdown fences."""


def run(state: ResearchState) -> dict[str, object]:
    """Add reflections and updated scores to hypotheses from the current iteration."""
    client = anthropic.Anthropic()
    iteration = state["iteration"]

    # Only reflect on hypotheses generated in this iteration
    current = [h for h in state["hypotheses"] if h["generation"] == iteration]
    if not current:
        return {
            "messages": [
                {"role": "agent", "agent": "reflection", "content": "no new hypotheses to reflect on"}
            ]
        }

    updated: list[Hypothesis] = []
    for hyp in current:
        prompt = f"Topic: {state['topic']}\nHypothesis: {hyp['text']}"
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        result: dict[str, object] = json.loads(message.content[0].text)
        updated.append(
            Hypothesis(
                id=hyp["id"],
                text=hyp["text"],
                score=float(result.get("score", 0.5)),  # type: ignore[arg-type]
                reflections=hyp["reflections"] + [str(result.get("critique", ""))],
                generation=hyp["generation"],
                evolved_from=hyp["evolved_from"],
            )
        )

    # Append updated versions — downstream agents use latest_hypotheses() to deduplicate
    return {
        "hypotheses": updated,
        "messages": [
            {
                "role": "agent",
                "agent": "reflection",
                "content": f"Reflected on {len(updated)} hypotheses (iteration {iteration})",
            }
        ],
    }
