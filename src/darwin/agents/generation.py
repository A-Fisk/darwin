"""Generation agent — produces new hypotheses each iteration."""
from __future__ import annotations

import uuid

import anthropic

from darwin.agents._common import latest_hypotheses, parse_json_response
from darwin.config import NEW_PER_ITERATION
from darwin.state import Hypothesis, ResearchState

_SYSTEM = """\
You are a creative scientific hypothesis generator.
Given a research topic, produce novel, specific, and testable hypotheses.

Output a JSON array of exactly {n} objects, each with a single key "text" (string).
Example: [{{"text": "..."}}, {{"text": "..."}}]
Output ONLY valid JSON — no prose, no markdown fences."""


def run(state: ResearchState) -> dict[str, object]:
    """Generate NEW_PER_ITERATION new hypotheses for the current iteration."""
    client = anthropic.Anthropic()

    existing = latest_hypotheses(state["hypotheses"])
    context = ""
    if existing:
        sample = existing[-5:]  # Show at most last 5 for context
        context = "\n\nExisting hypotheses (avoid repeating these):\n" + "\n".join(
            f"- {h['text']}" for h in sample
        )

    prompt = (
        f"Research topic: {state['topic']}{context}\n\n"
        f"Generate {NEW_PER_ITERATION} new, distinct hypotheses."
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM.format(n=NEW_PER_ITERATION),
        messages=[{"role": "user", "content": prompt}],
    )

    items: list[dict[str, str]] = parse_json_response(message)  # type: ignore[assignment]

    iteration = state["iteration"]
    new_hypotheses: list[Hypothesis] = []
    for item in items[:NEW_PER_ITERATION]:
        new_hypotheses.append(
            Hypothesis(
                id=uuid.uuid4().hex[:8],
                text=item["text"],
                score=0.5,
                reflections=[],
                generation=iteration,
                evolved_from=None,
            )
        )

    return {
        "hypotheses": new_hypotheses,
        "messages": [
            {
                "role": "agent",
                "agent": "generation",
                "content": f"Generated {len(new_hypotheses)} hypotheses (iteration {iteration})",
            }
        ],
    }
