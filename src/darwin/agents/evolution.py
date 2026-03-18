"""Evolution agent — mutates / combines top hypotheses into new candidates."""
from __future__ import annotations

import json
import uuid

import anthropic

from darwin.config import EVOLVED_PER_ITERATION
from darwin.state import Hypothesis, ResearchState

_SYSTEM = """\
You are a scientific hypothesis evolution engine.
Given a topic and a set of strong hypotheses, produce evolved variants by:
  - Combining ideas from multiple hypotheses
  - Extending a hypothesis with a new angle
  - Refining vague claims into more specific, testable forms

Output a JSON array of exactly {n} objects, each with:
  "text": the evolved hypothesis (string)
  "parent_id": the ID of the hypothesis this evolved from (string; pick the most relevant parent)

Output ONLY valid JSON — no prose, no markdown fences."""


def run(state: ResearchState) -> dict[str, object]:
    """Evolve EVOLVED_PER_ITERATION new hypotheses from top_hypotheses."""
    client = anthropic.Anthropic()

    parents = state.get("top_hypotheses") or []
    if not parents:
        return {
            "hypotheses": [],
            "messages": [{"role": "agent", "agent": "evolution", "content": "no top hypotheses to evolve"}],
        }

    parents_text = "\n".join(
        f'ID: {h["id"]} — {h["text"]}' for h in parents
    )
    prompt = (
        f"Topic: {state['topic']}\n\n"
        f"Top hypotheses to evolve:\n{parents_text}\n\n"
        f"Generate {EVOLVED_PER_ITERATION} evolved hypotheses."
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM.format(n=EVOLVED_PER_ITERATION),
        messages=[{"role": "user", "content": prompt}],
    )

    items: list[dict[str, str]] = json.loads(message.content[0].text)

    iteration = state["iteration"]
    parent_ids = {h["id"] for h in parents}

    evolved: list[Hypothesis] = []
    for item in items[:EVOLVED_PER_ITERATION]:
        parent_id = item.get("parent_id")
        # Validate parent_id exists; fall back to first parent
        if parent_id not in parent_ids:
            parent_id = parents[0]["id"]
        evolved.append(
            Hypothesis(
                id=uuid.uuid4().hex[:8],
                text=item["text"],
                score=0.5,
                reflections=[],
                generation=iteration,
                evolved_from=parent_id,
            )
        )

    return {
        "hypotheses": evolved,
        "messages": [
            {
                "role": "agent",
                "agent": "evolution",
                "content": f"Evolved {len(evolved)} hypotheses from {len(parents)} parents",
            }
        ],
    }
