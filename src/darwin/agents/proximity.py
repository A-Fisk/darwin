"""Proximity agent — clusters hypotheses by semantic similarity."""
from __future__ import annotations

import anthropic
from rich.console import Console

from darwin.agents._common import latest_hypotheses, parse_json_response
from darwin.state import ResearchState

_SYSTEM = """\
You are a semantic clustering expert for scientific hypotheses.
Given a list of hypotheses (numbered), group them by thematic/semantic similarity.

Output a JSON array of clusters, where each cluster is an array of hypothesis IDs (strings).
Every hypothesis ID must appear in exactly one cluster.

Example output: [["id1", "id3"], ["id2", "id4", "id5"]]
Output ONLY valid JSON — no prose, no markdown fences."""


def run(state: ResearchState) -> dict[str, object]:
    """Cluster hypotheses by semantic similarity using the LLM."""
    client = anthropic.Anthropic()
    console = Console()

    pool = latest_hypotheses(state["hypotheses"])
    if not pool:
        return {
            "proximity_clusters": [],
            "messages": [
                {"role": "agent", "agent": "proximity", "content": "no hypotheses to cluster"}
            ],
        }

    console.print(f"  [cyan]Clustering {len(pool)} hypotheses by semantic similarity...[/cyan]")

    hypotheses_text = "\n".join(
        f'ID: {h["id"]} — {h["text"]}' for h in pool
    )
    prompt = (
        f"Topic: {state['topic']}\n\n"
        f"Hypotheses:\n{hypotheses_text}\n\n"
        f"Group these {len(pool)} hypotheses into semantic clusters."
    )

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=_SYSTEM,
        messages=[
            {"role": "user", "content": prompt},
        ],
    )

    clusters: list[list[str]] = parse_json_response(message)  # type: ignore[assignment]

    # Validate: ensure all IDs are accounted for
    all_ids = {h["id"] for h in pool}
    clustered_ids = {hid for cluster in clusters for hid in cluster}
    unclustered = all_ids - clustered_ids
    if unclustered:
        clusters.append(list(unclustered))

    console.print(f"  [green]✓[/green] Formed {len(clusters)} clusters")

    return {
        "proximity_clusters": clusters,
        "messages": [
            {
                "role": "agent",
                "agent": "proximity",
                "content": f"Clustered {len(pool)} hypotheses into {len(clusters)} groups",
            }
        ],
    }
