"""Meta-review agent — cross-iteration quality audit."""
from __future__ import annotations

import anthropic

from darwin.agents._common import latest_hypotheses, parse_json_response, get_anthropic_client, get_default_model
from darwin.config import TOP_N_HYPOTHESES, MAX_TOKENS_DETAILED
from darwin.state import ResearchState

_SYSTEM = """\
You are a research quality auditor performing a cross-iteration review.
Given a topic, the current iteration, and the top hypotheses so far, assess overall progress.

Output a JSON object with:
  "decision": one of "continue", "stop", or "human_review"
  "notes": a brief audit summary (2-4 sentences)

Decision guidelines:
  "continue" — research is progressing; more iterations are likely to yield improvements
  "stop"     — hypotheses are high quality and sufficiently diverse; further iteration adds little
  "human_review" — research has stalled, results are ambiguous, or a key decision
                   requires human judgement

Output ONLY valid JSON — no prose, no markdown fences."""


def run(state: ResearchState) -> dict[str, object]:
    """Audit hypothesis quality across iterations and set supervisor_decision."""
    client = get_anthropic_client()
    model = get_default_model()

    pool = latest_hypotheses(state["hypotheses"])
    top = state.get("top_hypotheses") or pool[:TOP_N_HYPOTHESES]

    top_text = "\n".join(
        f'[score={h["score"]:.2f}] {h["text"]}' for h in top
    )
    prompt = (
        f"Topic: {state['topic']}\n"
        f"Iteration: {state['iteration']} / {state['max_iterations']}\n"
        f"Total hypotheses generated so far: {len(pool)}\n\n"
        f"Top hypotheses:\n{top_text}"
    )

    message = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS_DETAILED,
        system=_SYSTEM,
        messages=[
            {"role": "user", "content": prompt},
        ],
    )

    result: dict[str, str] = parse_json_response(message)  # type: ignore[assignment]
    decision = result.get("decision", "continue")
    if decision not in ("continue", "stop", "human_review"):
        decision = "continue"
    notes = result.get("notes", "")

    return {
        "supervisor_decision": decision,
        "meta_review_notes": notes,
        "messages": [
            {
                "role": "agent",
                "agent": "meta_review",
                "content": f"decision={decision}; {notes}",
            }
        ],
    }
