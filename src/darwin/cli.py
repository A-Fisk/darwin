"""CLI entry point for darwin co-scientist."""
from __future__ import annotations

import argparse
import time
import uuid
from typing import Any

from rich.markup import escape

from darwin.config import DEFAULT_MAX_ITERATIONS
from darwin.console import get_console, status_context

console = get_console()

# After a node completes, what spinner text to show while next node runs
_NEXT_STATUS: dict[str, str] = {
    "literature": "  ⟳ generation...",
    "generation": "  ⟳ reflection...",
    "reflection": "  ⟳ ranking...",
    "ranking": "  ⟳ proximity...",
    "proximity": "  ⟳ evolution...",
    "evolution": "  ⟳ meta_review...",
    "meta_review": "  ⟳ supervisor...",
    "human_review": "  ⟳ supervisor...",
}


def _get_next_phase(current_node: str) -> str | None:
    """Get the next phase name for timing purposes."""
    phase_order = {
        "supervisor": "literature",
        "literature": "generation",
        "generation": "reflection",
        "reflection": "ranking",
        "ranking": "proximity",
        "proximity": "evolution",
        "evolution": "meta_review",
        "meta_review": "supervisor",
        "human_review": "supervisor",
    }
    return phase_order.get(current_node)


def _print_verbose_output(node_name: str, update: dict[str, object]) -> None:
    """Print agent output details in verbose mode."""
    console.print(f"  [bold cyan]{node_name} output:[/bold cyan]")

    if node_name == "literature":
        papers: list[dict[str, object]] = update.get("literature_context") or []  # type: ignore[assignment]
        if papers:
            console.print(f"    [dim]fetched {len(papers)} papers[/dim]")
            for p in papers[:3]:
                title = escape(str(p.get("title", "")))
                console.print(f"    [yellow]•[/yellow] {title}")
            if len(papers) > 3:
                console.print(f"    [dim]... and {len(papers) - 3} more[/dim]")
        else:
            msgs: list[dict[str, object]] = update.get("messages") or []  # type: ignore[assignment]
            content = msgs[0]["content"] if msgs else "no papers fetched"
            console.print(f"    [dim]{content}[/dim]")

    elif node_name == "generation":
        hypotheses = update.get("hypotheses", [])
        for h in hypotheses:  # type: ignore[union-attr]
            txt = escape(h["text"])  # type: ignore[index]
            console.print(f"    [yellow]•[/yellow] ({h['id']}) {txt}")

    elif node_name == "reflection":
        hypotheses = update.get("hypotheses", [])
        for h in hypotheses:  # type: ignore[union-attr]
            score = h["score"]  # type: ignore[index]
            critique = h["reflections"][-1] if h["reflections"] else ""  # type: ignore[index]
            hid = h["id"]  # type: ignore[index]
            console.print(f"    [yellow]•[/yellow] ({hid}) score={score:.2f}")
            if critique:
                console.print(f"      [dim]{escape(str(critique))}[/dim]")

    elif node_name == "ranking":
        top = update.get("top_hypotheses", [])
        for i, h in enumerate(top, 1):  # type: ignore[union-attr]
            txt = escape(h["text"])  # type: ignore[index]
            line = f"    [yellow]{i}.[/yellow] ({h['id']}) score={h['score']:.2f} — {txt}"
            console.print(line)

    elif node_name == "evolution":
        hypotheses = update.get("hypotheses", [])
        for h in hypotheses:  # type: ignore[union-attr]
            parent = h.get("evolved_from", "?")  # type: ignore[union-attr]
            txt = escape(h["text"])  # type: ignore[index]
            console.print(f"    [yellow]•[/yellow] ({h['id']}) ← {parent}: {txt}")

    elif node_name == "meta_review":
        notes = update.get("meta_review_notes", "")
        if notes:
            console.print(f"    [dim]{notes}[/dim]")

    elif node_name == "supervisor":
        decision = update.get("supervisor_decision", "")
        if decision:
            console.print(f"    decision: [bold]{decision}[/bold]")


def _stream_with_progress(
    graph: Any,
    state_input: Any,
    config: dict[str, object],
    max_iterations: int,
    verbose: bool = False,
) -> None:
    """Stream one graph pass, printing per-node progress via Rich Status."""
    # Track timing for each phase when verbose is enabled
    phase_timings: dict[str, float] = {}
    phase_start_time: dict[str, float] = {}

    with status_context("  ⟳ supervisor...", spinner="dots") as status:
        for event in graph.stream(state_input, config=config, stream_mode="updates"):
            node_name, update = next(iter(event.items()))

            # Skip internal LangGraph bookkeeping events
            if node_name.startswith("__"):
                continue

            # Record phase completion time if timing is being tracked
            current_time = time.time()
            if verbose and node_name in phase_start_time:
                duration = current_time - phase_start_time[node_name]
                phase_timings[node_name] = duration

            console.print(f"  [green]✓[/green] {node_name}")

            # Show timing information for major phases when verbose
            if verbose and node_name in phase_timings:
                duration = phase_timings[node_name]
                console.print(f"    [dim]completed in {duration:.2f}s[/dim]")

            if verbose:
                _print_verbose_output(node_name, update)

            # Set start time for next phase when verbose
            if verbose:
                next_phase = _get_next_phase(node_name)
                if next_phase:
                    phase_start_time[next_phase] = current_time

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
                    status.update("  ⟳ literature...")
                    if verbose:
                        phase_start_time["literature"] = current_time
                elif decision == "human_review":
                    status.update("  ⟳ human_review...")
                    if verbose:
                        phase_start_time["human_review"] = current_time
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
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print each agent's raw output and execution timing as it completes",
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=None,
        help="Write hypotheses.tex and references.bib to DIR on completion",
    )
    parser.add_argument(
        "--output-file",
        metavar="FILE",
        default=None,
        help="Write human-readable text summary to FILE on completion",
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
        "literature_context": [],
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

    # Track total execution time when verbose
    start_time = time.time()
    state_input: Any = initial_state

    while True:
        _stream_with_progress(graph, state_input, config, args.iterations, verbose=args.verbose)

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

    # Show total execution time when verbose
    if args.verbose:
        total_time = time.time() - start_time
        console.print(f"\n[bold green]Total execution time: {total_time:.2f}s[/bold green]")

    final_state: dict[str, object] = graph.get_state(config).values  # type: ignore[assignment]
    final_hypotheses: list = final_state.get("final_hypotheses", [])  # type: ignore[assignment]
    meta_review_notes = str(final_state.get("meta_review_notes", ""))
    display_final_results(
        final_hypotheses=final_hypotheses,
        meta_review_notes=meta_review_notes,
        topic=args.topic,
    )

    if args.output_dir:
        from darwin.output import write_output

        literature_context: list = final_state.get("literature_context", [])  # type: ignore[assignment]
        write_output(
            output_dir=args.output_dir,
            hypotheses=final_hypotheses,
            literature_context=literature_context,
            topic=args.topic,
            meta_review_notes=meta_review_notes,
        )
        console.print(
            f"Output written to {args.output_dir}/hypotheses.tex and"
            f" {args.output_dir}/references.bib"
        )

    if args.output_file:
        from darwin.output import write_text_output

        write_text_output(
            output_file=args.output_file,
            hypotheses=final_hypotheses,
            literature_context=literature_context,
            topic=args.topic,
            meta_review_notes=meta_review_notes,
            max_iterations=args.iterations,
        )
        console.print(f"Text summary written to {args.output_file}")
