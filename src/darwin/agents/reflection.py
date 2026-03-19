"""Reflection agent — critiques and scores each hypothesis."""
from __future__ import annotations

import anthropic
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from darwin.agents._common import criteria_prompt_block, parse_json_response
from darwin.config import MAX_TOKENS_DETAILED
from darwin.state import Hypothesis, ResearchState

_SYSTEM = """\
You are a rigorous scientific critic evaluating research hypotheses.
Given a topic and a hypothesis, critique its scientific merit.

Evaluate using these criteria:
{criteria}

Output a JSON object with exactly two keys:
  "critique": a concise critique (1-3 sentences)
  "score": a float 0.0–1.0 (1.0 = excellent across all criteria; 0.0 = poor)

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
                {
                    "role": "agent",
                    "agent": "reflection",
                    "content": "no new hypotheses to reflect on",
                }
            ]
        }

    criteria_block = criteria_prompt_block()
    system = _SYSTEM.format(criteria=criteria_block)

    # Build literature index for reference checking
    lit_context: list[dict[str, str]] = state.get("literature_context") or []
    lit_index: dict[str, str] = {}
    for p in lit_context:
        pid = p.get("paper_id", "")
        if pid:
            lit_index[pid] = p.get("title", "")

    updated: list[Hypothesis] = []
    console = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(f"[cyan]Reflecting on {len(current)} hypotheses", total=len(current))

        for i, hyp in enumerate(current):
            # Update progress bar with current hypothesis
            progress.update(task, advance=1, description=f"[cyan]Critiquing hypothesis {hyp['id'][:4]} ({i+1}/{len(current)})")

            lit_note = ""
            if lit_index:
                cited_titles = [
                    lit_index[ref] for ref in hyp.get("references", []) if ref in lit_index
                ]
                if cited_titles:
                    lit_note = f"\nCited papers: {'; '.join(cited_titles)}"
                else:
                    lit_note = "\nNo papers cited."

            prompt = f"Topic: {state['topic']}\nHypothesis: {hyp['text']}{lit_note}"
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=MAX_TOKENS_DETAILED,
                system=system,
                messages=[
                    {"role": "user", "content": prompt},
                ],
            )
            result: dict[str, object] = parse_json_response(message)  # type: ignore[assignment]
            updated.append(
                Hypothesis(
                    id=hyp["id"],
                    text=hyp["text"],
                    score=float(result.get("score", 0.5)),  # type: ignore[arg-type]
                    reflections=hyp["reflections"] + [str(result.get("critique", ""))],
                    generation=hyp["generation"],
                    evolved_from=hyp["evolved_from"],
                    references=hyp.get("references", []),
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
