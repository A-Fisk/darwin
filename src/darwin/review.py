"""Human review UX — rich hypothesis table and interactive feedback prompt."""
from __future__ import annotations

from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from darwin.console import get_console
from darwin.state import Hypothesis

console = get_console()


def display_hypotheses_table(
    hypotheses: list[Hypothesis],
    iteration: int,
    meta_review_notes: str = "",
) -> None:
    """Render a rich table of hypotheses with scores and provenance."""
    table = Table(
        title=f"Hypotheses — Iteration {iteration}",
        show_header=True,
        header_style="bold cyan",
        border_style="blue",
        expand=True,
    )
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Hypothesis", style="white", ratio=6)
    table.add_column("Score", justify="right", style="bold green", width=8)
    table.add_column("Gen", justify="center", style="dim", width=5)
    table.add_column("Evolved From", style="dim", width=14)

    for i, h in enumerate(hypotheses, 1):
        score_display = f"{h['score']:.4f}"
        gen_display = str(h["generation"])
        evolved = h["evolved_from"] or "—"
        table.add_row(str(i), h["text"], score_display, gen_display, evolved)

    console.print(table)

    if meta_review_notes:
        console.print(
            Panel(
                meta_review_notes,
                title="[bold yellow]Meta-Review Notes[/bold yellow]",
                border_style="yellow",
                expand=False,
            )
        )


def prompt_human(
    top_hypotheses: list[Hypothesis],
    meta_review_notes: str,
    iteration: int,
) -> str:
    """Display the review table and prompt for [C]ontinue / [S]top / [F]eedback.

    Returns the raw feedback string.  Returning "stop" signals the graph to end.
    """
    console.print()
    display_hypotheses_table(top_hypotheses, iteration, meta_review_notes)
    console.print()
    console.print("[bold]Human Review[/bold]")
    console.print("  [cyan][C][/cyan]  Continue to next iteration")
    console.print("  [red][S][/red]  Stop and produce final results")
    console.print("  [yellow][F][/yellow]  Provide feedback and continue")
    console.print()

    choice = Prompt.ask(
        "[bold]Choice[/bold]",
        choices=["c", "s", "f", "C", "S", "F"],
        default="C",
    ).upper()

    if choice == "S":
        return "stop"
    if choice == "C":
        return "continue"

    # "F" — collect free-form feedback
    feedback = Prompt.ask("[bold yellow]Feedback[/bold yellow]")
    return feedback.strip() or "continue"


def display_final_results(
    final_hypotheses: list[Hypothesis],
    meta_review_notes: str,
    topic: str,
    literature_context: list[dict[str, str]] | None = None,
) -> None:
    """Render the final ranked hypothesis list and meta-review summary with numbered references."""
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{topic}[/bold cyan]",
            title="[bold green]Research Complete[/bold green]",
            border_style="green",
            expand=False,
        )
    )
    console.print()

    if not final_hypotheses:
        console.print("[dim]No final hypotheses recorded.[/dim]")
        return

    # Build reference mapping if literature context is available
    paper_id_to_num: dict[str, int] = {}
    reference_list: list[dict[str, str]] = []

    if literature_context:
        # Collect all unique paper IDs referenced across hypotheses
        all_refs: set[str] = set()
        for h in final_hypotheses:
            refs: list[str] = h.get("references", [])
            all_refs.update(refs)

        # Create ordered mapping from paper_id to reference number
        for i, paper_id in enumerate(sorted(all_refs), 1):
            paper_id_to_num[paper_id] = i
            # Find the paper details in literature context
            for paper in literature_context:
                if paper.get("paper_id") == paper_id:
                    reference_list.append(paper)
                    break

    table = Table(
        title="Final Ranked Hypotheses",
        show_header=True,
        header_style="bold magenta",
        border_style="magenta",
        expand=True,
        show_lines=True,
    )
    table.add_column("Rank", style="bold", width=6, justify="right")
    table.add_column("Hypothesis", style="white", ratio=6)
    table.add_column("Score", justify="right", style="bold green", width=8)
    table.add_column("Gen", justify="center", style="dim", width=5)

    for rank, h in enumerate(final_hypotheses, 1):
        hypothesis_text = h["text"]

        # Add numbered references to hypothesis text if available
        if literature_context and paper_id_to_num:
            refs: list[str] = h.get("references", [])
            if refs:
                # Get reference numbers for this hypothesis
                ref_nums = [paper_id_to_num[ref_id] for ref_id in refs if ref_id in paper_id_to_num]
                if ref_nums:
                    ref_nums.sort()
                    ref_str = ",".join(str(n) for n in ref_nums)
                    hypothesis_text = f"{hypothesis_text} [{ref_str}]"

        table.add_row(
            f"#{rank}",
            hypothesis_text,
            f"{h['score']:.4f}",
            str(h["generation"]),
        )

    console.print(table)

    # Display reference list if available
    if reference_list:
        console.print()
        ref_table = Table(
            title="References",
            show_header=False,
            border_style="cyan",
            expand=True,
        )
        ref_table.add_column("Reference", style="white")

        for i, paper in enumerate(reference_list, 1):
            authors = paper.get("authors", "Unknown authors")
            year = paper.get("year", "Unknown year")
            title = paper.get("title", "Unknown title")
            venue = paper.get("venue", "")

            # Format: [1] Author et al. (Year). Title. Journal.
            citation = f"[{i}] {authors} ({year}). {title}."
            if venue:
                citation += f" {venue}."

            ref_table.add_row(citation)

        console.print(ref_table)

    if meta_review_notes:
        console.print()
        console.print(
            Panel(
                meta_review_notes,
                title="[bold yellow]Meta-Review Summary[/bold yellow]",
                border_style="yellow",
                expand=False,
            )
        )
