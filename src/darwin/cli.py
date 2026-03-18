"""CLI entry point for darwin co-scientist."""
from __future__ import annotations

import argparse

from rich.console import Console

from darwin.config import DEFAULT_MAX_ITERATIONS

console = Console()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Darwin AI Co-Scientist — multi-agent research hypothesis system"
    )
    parser.add_argument("topic", help="Research question or domain to investigate")
    parser.add_argument(
        "--iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Maximum number of iterations (default: {DEFAULT_MAX_ITERATIONS})",
    )
    args = parser.parse_args()

    from darwin.graph import build_graph

    graph = build_graph()

    initial_state = {
        "topic": args.topic,
        "max_iterations": args.iterations,
        "iteration": 0,
        "hypotheses": [],
        "ranked_ids": [],
        "top_hypotheses": [],
        "proximity_clusters": [],
        "supervisor_decision": "continue",
        "meta_review_notes": "",
        "human_feedback": None,
        "final_hypotheses": [],
        "messages": [],
    }

    console.print(f"[bold green]Darwin Co-Scientist[/bold green]")
    console.print(f"Topic: [cyan]{args.topic}[/cyan]")
    console.print(f"Max iterations: {args.iterations}")
    console.print()

    result = graph.invoke(initial_state)

    console.print("\n[bold]Final Hypotheses:[/bold]")
    for i, h in enumerate(result.get("final_hypotheses", []), 1):
        console.print(f"  {i}. [yellow]{h['text']}[/yellow] (score: {h['score']:.2f})")
