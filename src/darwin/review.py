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
) -> None:
    """Render the final ranked hypothesis list and meta-review summary."""
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
        table.add_row(
            f"#{rank}",
            h["text"],
            f"{h['score']:.4f}",
            str(h["generation"]),
        )

    console.print(table)

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
