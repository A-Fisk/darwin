"""Tests for the review module (rich display + human-review UX)."""
from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from darwin.review import display_final_results, display_hypotheses_table, prompt_human
from darwin.state import Hypothesis


def _make_hypothesis(
    id: str = "abc",
    text: str = "Test hypothesis",
    score: float = 0.75,
    generation: int = 1,
    evolved_from: str | None = None,
    references: list[str] | None = None,
) -> Hypothesis:
    return Hypothesis(
        id=id,
        text=text,
        score=score,
        reflections=[],
        generation=generation,
        evolved_from=evolved_from,
        references=references or [],
    )


class TestDisplayHypothesesTable:
    def test_renders_without_error(self) -> None:
        buf = StringIO()
        con = Console(file=buf, no_color=True)
        with patch("darwin.review.console", con):
            display_hypotheses_table([_make_hypothesis()], iteration=1)
        output = buf.getvalue()
        assert "Test hypothesis" in output
        assert "0.7500" in output

    def test_shows_meta_review_notes(self) -> None:
        buf = StringIO()
        con = Console(file=buf, no_color=True)
        with patch("darwin.review.console", con):
            display_hypotheses_table(
                [_make_hypothesis()], iteration=2, meta_review_notes="Some notes"
            )
        assert "Some notes" in buf.getvalue()

    def test_empty_hypotheses(self) -> None:
        buf = StringIO()
        con = Console(file=buf, no_color=True)
        with patch("darwin.review.console", con):
            display_hypotheses_table([], iteration=0)
        # Should not raise; table renders with no rows.


class TestPromptHuman:
    def test_continue_choice_returns_continue(self) -> None:
        buf = StringIO()
        con = Console(file=buf, no_color=True)
        with patch("darwin.review.console", con), patch(
            "darwin.review.Prompt.ask", return_value="c"
        ):
            result = prompt_human([_make_hypothesis()], meta_review_notes="", iteration=1)
        assert result == "continue"

    def test_stop_choice_returns_stop(self) -> None:
        buf = StringIO()
        con = Console(file=buf, no_color=True)
        with patch("darwin.review.console", con), patch(
            "darwin.review.Prompt.ask", return_value="s"
        ):
            result = prompt_human([_make_hypothesis()], meta_review_notes="", iteration=1)
        assert result == "stop"

    def test_feedback_choice_returns_feedback_text(self) -> None:
        buf = StringIO()
        con = Console(file=buf, no_color=True)
        with patch("darwin.review.console", con), patch(
            "darwin.review.Prompt.ask", side_effect=["f", "more detail please"]
        ):
            result = prompt_human([_make_hypothesis()], meta_review_notes="", iteration=1)
        assert result == "more detail please"

    def test_feedback_empty_falls_back_to_continue(self) -> None:
        buf = StringIO()
        con = Console(file=buf, no_color=True)
        with patch("darwin.review.console", con), patch(
            "darwin.review.Prompt.ask", side_effect=["f", ""]
        ):
            result = prompt_human([_make_hypothesis()], meta_review_notes="", iteration=1)
        assert result == "continue"


class TestDisplayFinalResults:
    def test_renders_final_hypotheses(self) -> None:
        buf = StringIO()
        con = Console(file=buf, no_color=True)
        hyps = [_make_hypothesis(text="Top hypothesis", score=0.9)]
        with patch("darwin.review.console", con):
            display_final_results(hyps, meta_review_notes="Good results", topic="cancer", literature_context=None)
        output = buf.getvalue()
        assert "Top hypothesis" in output
        assert "0.9000" in output
        assert "Good results" in output

    def test_empty_final_hypotheses(self) -> None:
        buf = StringIO()
        con = Console(file=buf, no_color=True)
        with patch("darwin.review.console", con):
            display_final_results([], meta_review_notes="", topic="test", literature_context=None)
        assert "No final hypotheses" in buf.getvalue()

    def test_displays_numbered_references(self) -> None:
        """Test that numbered references are added to hypotheses and reference list is shown."""
        buf = StringIO()
        con = Console(file=buf, no_color=True)

        # Create hypothesis with references
        hyps = [_make_hypothesis(
            text="Sleep spindles correlate with memory",
            references=["paper1", "paper2"]
        )]

        # Create literature context
        literature_context = [
            {
                "paper_id": "paper1",
                "title": "Sleep Spindles in Memory Formation",
                "authors": "Smith et al.",
                "year": "2023",
                "venue": "Nature Neuroscience"
            },
            {
                "paper_id": "paper2",
                "title": "Memory Consolidation During Sleep",
                "authors": "Johnson and Brown",
                "year": "2022",
                "venue": "Journal of Sleep Research"
            }
        ]

        with patch("darwin.review.console", con):
            display_final_results(hyps, meta_review_notes="", topic="sleep", literature_context=literature_context)

        output = buf.getvalue()
        # Check that hypothesis has numbered references
        assert "Sleep spindles correlate with memory [1,2]" in output
        # Check that reference list is displayed
        assert "[1] Smith et al. (2023). Sleep Spindles in Memory Formation." in output
        assert "Nature" in output and "Neuroscience" in output
        assert "[2] Johnson and Brown (2022). Memory Consolidation During Sleep." in output
        assert "Journal of" in output and "Sleep Research" in output
