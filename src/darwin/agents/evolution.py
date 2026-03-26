"""Evolution agent — mutates / combines top hypotheses into new candidates."""
from __future__ import annotations

import uuid

import anthropic

from darwin.agents._common import parse_json_response
from darwin.config import EVOLVED_PER_ITERATION, MAX_TOKENS_CREATIVE
from darwin.console import print_safe, progress_context
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
    from darwin.debug_modes import should_mock_agent, artificial_delay

    parents = state.get("top_hypotheses") or []
    if not parents:
        return {
            "hypotheses": [],
            "messages": [
                {"role": "agent", "agent": "evolution", "content": "no top hypotheses to evolve"}
            ],
        }

    # Check if we should use mock evolution
    if should_mock_agent("evolution"):
        artificial_delay()
        # Simple mock evolution - just create variations of existing hypotheses
        evolved = []
        iteration = state["iteration"]

        for i in range(min(EVOLVED_PER_ITERATION, len(parents))):
            parent = parents[i]
            # Simple text variation for mock
            evolved_text = parent["text"].replace("hypothesis", "evolved hypothesis")
            if evolved_text == parent["text"]:  # If no replacement happened
                evolved_text = f"Enhanced version of {parent['text'][:50]}..."

            evolved.append(
                Hypothesis(
                    id=uuid.uuid4().hex[:8],
                    text=evolved_text,
                    score=0.5,
                    reflections=[],
                    generation=iteration,
                    evolved_from=parent["id"],
                    references=parent.get("references", []),
                )
            )

        print_safe(f"  [green]✓[/green] Evolved {len(evolved)} hypotheses (debug mode)")

        return {
            "hypotheses": evolved,
            "messages": [
                {
                    "role": "agent",
                    "agent": "evolution",
                    "content": f"Evolved {len(evolved)} hypotheses from {len(parents)} parents (debug mode)",
                }
            ],
        }

    client = anthropic.Anthropic()

    parents = state.get("top_hypotheses") or []
    if not parents:
        return {
            "hypotheses": [],
            "messages": [
                {"role": "agent", "agent": "evolution", "content": "no top hypotheses to evolve"}
            ],
        }

    with progress_context(
        f"Evolving {EVOLVED_PER_ITERATION} hypotheses from {len(parents)} parents"
    ) as progress:
        task = progress.add_task("[cyan]Evolving hypotheses", total=1)

        parents_text = "\n".join(
            f'ID: {h["id"]} — {h["text"]}' for h in parents
        )
        prompt = (
            f"Topic: {state['topic']}\n\n"
            f"Top hypotheses to evolve:\n{parents_text}\n\n"
            f"Generate {EVOLVED_PER_ITERATION} evolved hypotheses."
        )

        progress.update(
            task,
            advance=0,
            description=f"[cyan]Requesting {EVOLVED_PER_ITERATION} evolved hypotheses...",
        )

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=MAX_TOKENS_CREATIVE,
            system=_SYSTEM.format(n=EVOLVED_PER_ITERATION),
            messages=[
                {"role": "user", "content": prompt},
            ],
        )

        progress.update(
            task,
            advance=0.5,
            description="[cyan]Parsing response and creating evolved hypotheses...",
        )

        items: list[dict[str, str]] = parse_json_response(message)  # type: ignore[assignment]

        iteration = state["iteration"]
        verbose_level = state.get("verbose_level", 0)
        parent_ids = {h["id"] for h in parents}

        evolved: list[Hypothesis] = []
        for i, item in enumerate(items[:EVOLVED_PER_ITERATION], 1):
            progress.update(
                task,
                advance=0,
                description=f"[cyan]Creating evolved hypothesis {i}/{EVOLVED_PER_ITERATION}...",
            )
            parent_id = item.get("parent_id")
            # Validate parent_id exists; fall back to first parent
            if parent_id not in parent_ids:
                parent_id = parents[0]["id"]

            hypothesis_text = item["text"]
            evolved.append(
                Hypothesis(
                    id=uuid.uuid4().hex[:8],
                    text=hypothesis_text,
                    score=0.5,
                    reflections=[],
                    generation=iteration,
                    evolved_from=parent_id,
                    references=[],
                )
            )

            # Stream evolved hypothesis immediately in super verbose mode
            if verbose_level >= 2:
                print_safe(f"  [green]✓ E{i}:[/green] {hypothesis_text}")

        progress.update(
            task, advance=0.5, description=f"[cyan]Generated {len(evolved)} evolved hypotheses!"
        )
        progress.update(task, completed=1)

    print_safe(f"  [green]✓[/green] Generated {len(evolved)} evolved hypotheses")

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
