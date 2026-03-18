"""CLI entry point for darwin co-scientist."""
from __future__ import annotations

import argparse
import uuid

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

    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.types import Command

    from darwin.graph import build_graph
    from darwin.review import display_final_results, prompt_human

    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    config: dict[str, object] = {"configurable": {"thread_id": str(uuid.uuid4())}}

    initial_state: dict[str, object] = {
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

    console.print("[bold green]Darwin Co-Scientist[/bold green]")
    console.print(f"Topic: [cyan]{args.topic}[/cyan]")
    console.print(f"Max iterations: {args.iterations}")
    console.print()

    result: dict[str, object] = graph.invoke(initial_state, config=config)

    # Handle human-review interrupts in a loop until the graph finishes.
    while True:
        state_snapshot = graph.get_state(config)
        interrupts = [
            intr
            for task in state_snapshot.tasks
            for intr in task.interrupts
        ]
        if not interrupts:
            break

        intr_val: dict[str, object] = interrupts[0].value  # type: ignore[assignment]
        feedback = prompt_human(
            top_hypotheses=intr_val.get("top_hypotheses", []),  # type: ignore[arg-type]
            meta_review_notes=str(intr_val.get("meta_review_notes", "")),
            iteration=int(intr_val.get("iteration", 0)),
        )
        result = graph.invoke(Command(resume=feedback), config=config)

    display_final_results(
        final_hypotheses=result.get("final_hypotheses", []),  # type: ignore[arg-type]
        meta_review_notes=str(result.get("meta_review_notes", "")),
        topic=args.topic,
    )
