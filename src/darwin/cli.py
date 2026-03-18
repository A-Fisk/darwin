"""CLI entry point for darwin co-scientist."""
from __future__ import annotations

import argparse
import uuid
from typing import Any

from rich.console import Console

from darwin.config import DEFAULT_MAX_ITERATIONS

console = Console()

# After a node completes, what spinner text to show while next node runs
_NEXT_STATUS: dict[str, str] = {
    "generation": "  ⟳ reflection...",
    "reflection": "  ⟳ ranking...",
    "ranking": "  ⟳ proximity...",
    "proximity": "  ⟳ evolution...",
    "evolution": "  ⟳ meta_review...",
    "meta_review": "  ⟳ supervisor...",
    "human_review": "  ⟳ supervisor...",
}


def _stream_with_progress(
    graph: Any,
    state_input: Any,
    config: dict[str, object],
    max_iterations: int,
) -> None:
    """Stream one graph pass, printing per-node progress via Rich Status."""
    with console.status("  ⟳ supervisor...", spinner="dots") as status:
        for event in graph.stream(state_input, config=config, stream_mode="updates"):
            node_name, update = next(iter(event.items()))

            # Skip internal LangGraph bookkeeping events
            if node_name.startswith("__"):
                continue

            console.print(f"  [green]✓[/green] {node_name}")

            if node_name == "supervisor":
                iteration: int = int(update.get("iteration", 0))
                decision: str = str(update.get("supervisor_decision", "continue"))

                # Show previous iteration's decision (not on the very first run)
                if iteration > 1:
                    if decision == "continue":
                        console.print("  [dim]→ continuing[/dim]")
                    elif decision == "stop":
                        console.print("  [dim]→ stopping[/dim]")
                    elif decision == "human_review":
                        console.print("  [dim]→ human review requested[/dim]")

                console.print(f"\n[bold]Iteration {iteration}/{max_iterations}[/bold]")

                if decision == "continue":
                    status.update("  ⟳ generation...")
                elif decision == "human_review":
                    status.update("  ⟳ human_review...")
                # "stop" → stream will end after this node

            elif node_name == "ranking":
                ranked_ids = update.get("ranked_ids", [])
                if ranked_ids:
                    console.print(f"  [dim]{len(ranked_ids)} hypotheses ranked[/dim]")
                status.update(_NEXT_STATUS.get(node_name, ""))

            else:
                next_status = _NEXT_STATUS.get(node_name)
                if next_status:
                    status.update(next_status)


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

    state_input: Any = initial_state

    while True:
        _stream_with_progress(graph, state_input, config, args.iterations)

        # Check for human-review interrupts
        state_snapshot = graph.get_state(config)
        interrupts = [
            intr
            for task in state_snapshot.tasks
            for intr in task.interrupts
        ]
        if not interrupts:
            break

        intr_val: dict[str, object] = interrupts[0].value  # type: ignore[assignment]
        console.print()
        feedback = prompt_human(
            top_hypotheses=intr_val.get("top_hypotheses", []),  # type: ignore[arg-type]
            meta_review_notes=str(intr_val.get("meta_review_notes", "")),
            iteration=int(intr_val.get("iteration", 0)),
        )
        state_input = Command(resume=feedback)
        console.print()

    final_state: dict[str, object] = graph.get_state(config).values  # type: ignore[assignment]
    display_final_results(
        final_hypotheses=final_state.get("final_hypotheses", []),  # type: ignore[arg-type]
        meta_review_notes=str(final_state.get("meta_review_notes", "")),
        topic=args.topic,
    )
