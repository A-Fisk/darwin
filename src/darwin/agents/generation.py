"""Generation agent — produces new hypotheses each iteration."""
from __future__ import annotations

import uuid

import anthropic

from darwin.agents._common import latest_hypotheses, parse_json_response
from darwin.config import MAX_TOKENS_CREATIVE, NEW_PER_ITERATION
from darwin.console import print_safe, progress_context
from darwin.state import Hypothesis, ResearchState

_SYSTEM_BASE = """\
You are a creative scientific hypothesis generator.
Given a research topic, produce novel, specific, and testable hypotheses.

Output a JSON array of exactly {n} objects. Each object must have:
  "text": the hypothesis statement (string)
  "references": list of paper_id strings from the literature that this hypothesis builds on
                (use [] if none apply)

Example:
[
  {{"text": "...", "references": ["abc123"]}},
  {{"text": "...", "references": []}}
]
Output ONLY valid JSON — no prose, no markdown fences."""

_SYSTEM_NO_LIT = """\
You are a creative scientific hypothesis generator.
Given a research topic, produce novel, specific, and testable hypotheses.

Output a JSON array of exactly {n} objects, each with:
  "text": the hypothesis statement (string)
  "references": [] (empty list)

Example: [{{"text": "...", "references": []}}, {{"text": "...", "references": []}}]
Output ONLY valid JSON — no prose, no markdown fences."""


def run(state: ResearchState) -> dict[str, object]:
    """Generate NEW_PER_ITERATION new hypotheses for the current iteration."""
    # Add timeout to prevent hanging on API calls
    client = anthropic.Anthropic(timeout=60.0)  # 60 second timeout

    existing = latest_hypotheses(state["hypotheses"])
    context = ""
    if existing:
        sample = existing[-5:]  # Show at most last 5 for context
        context = "\n\nExisting hypotheses (avoid repeating these):\n" + "\n".join(
            f"- {h['text']}" for h in sample
        )

    lit_context: list[dict[str, str]] = state.get("literature_context") or []
    with progress_context(f"Generating {NEW_PER_ITERATION} new hypotheses") as progress:
        task = progress.add_task("[cyan]Generating hypotheses", total=1)

        if lit_context:
            lit_lines = []
            for p in lit_context:
                pid = p.get("paper_id", "")
                title = p.get("title", "")
                abstract = p.get("abstract", "")
                authors = p.get("authors", "")
                lit_lines.append(
                    f"[{pid}] {title} ({authors})\n  Abstract: {abstract}"
                )
            lit_block = (
                "\n\nRelevant literature (cite paper_ids in your references):\n"
                + "\n\n".join(lit_lines)
            )
            system = _SYSTEM_BASE.format(n=NEW_PER_ITERATION)
            prompt = (
                f"Research topic: {state['topic']}{context}{lit_block}\n\n"
                f"Generate {NEW_PER_ITERATION} new, distinct hypotheses that extend, "
                f"challenge, or synthesise from the retrieved papers — not just rehash them. "
                f"Cite paper_ids that support each hypothesis."
            )
        else:
            system = _SYSTEM_NO_LIT.format(n=NEW_PER_ITERATION)
            prompt = (
                f"Research topic: {state['topic']}{context}\n\n"
                f"Generate {NEW_PER_ITERATION} new, distinct hypotheses."
            )

        progress.update(
            task,
            advance=0,
            description=f"[cyan]Requesting {NEW_PER_ITERATION} hypotheses from Claude...",
        )

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=MAX_TOKENS_CREATIVE,
            system=system,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )

        progress.update(
            task,
            advance=0.5,
            description="[cyan]Parsing response and creating hypothesis objects...",
        )

        items: list[dict[str, object]] = parse_json_response(message)  # type: ignore[assignment]

        iteration = state["iteration"]
        verbose_level = state.get("verbose_level", 0)
        new_hypotheses: list[Hypothesis] = []
        for i, item in enumerate(items[:NEW_PER_ITERATION], 1):
            progress.update(
                task, advance=0, description=f"[cyan]Creating hypothesis {i}/{NEW_PER_ITERATION}..."
            )
            refs: list[str] = []
            raw_refs = item.get("references", [])
            if isinstance(raw_refs, list):
                refs = [str(r) for r in raw_refs]

            hypothesis_text = str(item["text"])
            new_hypotheses.append(
                Hypothesis(
                    id=uuid.uuid4().hex[:8],
                    text=hypothesis_text,
                    score=0.5,
                    reflections=[],
                    generation=iteration,
                    evolved_from=None,
                    references=refs,
                )
            )

            # Stream hypothesis immediately in super verbose mode
            if verbose_level >= 2:
                print_safe(f"  [green]✓ H{i}:[/green] {hypothesis_text}")

        progress.update(
            task, advance=0.5, description=f"[cyan]Generated {len(new_hypotheses)} hypotheses!"
        )
        progress.update(task, completed=1)

    print_safe(f"  [green]✓[/green] Generated {len(new_hypotheses)} hypotheses")

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
