"""Tests for the CLI --verbose flag."""
from __future__ import annotations

import sys
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from darwin.cli import _print_verbose_output, _stream_with_progress, main


class TestPrintVerboseOutput:
    def test_generation_prints_hypotheses(self, capsys) -> None:
        update = {
            "hypotheses": [
                {"id": "abc123", "text": "Hypothesis text here", "score": 0.5,
                 "reflections": [], "generation": 1, "evolved_from": None}
            ]
        }
        _print_verbose_output("generation", update)
        out = capsys.readouterr().out
        assert "(abc123)" in out
        assert "Hypothesis text here" in out

    def test_reflection_prints_score_and_critique(self, capsys) -> None:
        update = {
            "hypotheses": [
                {"id": "def456", "text": "Some hypothesis", "score": 0.75,
                 "reflections": ["This is a critique"], "generation": 1, "evolved_from": None}
            ]
        }
        _print_verbose_output("reflection", update)
        out = capsys.readouterr().out
        assert "(def456)" in out
        assert "0.75" in out
        assert "This is a critique" in out

    def test_ranking_prints_top_hypotheses(self, capsys) -> None:
        update = {
            "top_hypotheses": [
                {"id": "h1", "text": "Top hypothesis", "score": 0.9,
                 "reflections": [], "generation": 1, "evolved_from": None}
            ]
        }
        _print_verbose_output("ranking", update)
        out = capsys.readouterr().out
        assert "(h1)" in out
        assert "0.90" in out
        assert "Top hypothesis" in out

    def test_evolution_prints_evolved_hypotheses(self, capsys) -> None:
        update = {
            "hypotheses": [
                {"id": "e1", "text": "Evolved idea", "score": 0.5,
                 "reflections": [], "generation": 2, "evolved_from": "parent01"}
            ]
        }
        _print_verbose_output("evolution", update)
        out = capsys.readouterr().out
        assert "(e1)" in out
        assert "parent01" in out
        assert "Evolved idea" in out

    def test_meta_review_prints_notes(self, capsys) -> None:
        update = {"meta_review_notes": "Research is progressing well."}
        _print_verbose_output("meta_review", update)
        out = capsys.readouterr().out
        assert "Research is progressing well." in out

    def test_supervisor_prints_decision(self, capsys) -> None:
        update = {"supervisor_decision": "continue"}
        _print_verbose_output("supervisor", update)
        out = capsys.readouterr().out
        assert "continue" in out

    def test_unknown_node_prints_header_only(self, capsys) -> None:
        update = {}
        _print_verbose_output("proximity", update)
        out = capsys.readouterr().out
        assert "proximity output" in out

    def test_empty_update_no_crash(self, capsys) -> None:
        _print_verbose_output("generation", {})
        _print_verbose_output("reflection", {})
        _print_verbose_output("ranking", {})
        _print_verbose_output("evolution", {})
        _print_verbose_output("meta_review", {})
        _print_verbose_output("supervisor", {})


class TestStreamWithProgressVerbose:
    def _make_graph(self, events: list[dict]) -> MagicMock:
        graph = MagicMock()
        graph.stream.return_value = iter(events)
        return graph

    def test_verbose_calls_print_verbose_output(self) -> None:
        events = [
            {"supervisor": {"iteration": 1, "supervisor_decision": "stop"}},
        ]
        graph = self._make_graph(events)
        with patch("darwin.cli._print_verbose_output") as mock_print_verbose:
            _stream_with_progress(graph, {}, {}, max_iterations=3, verbose=True)
        mock_print_verbose.assert_called_once_with("supervisor", {"iteration": 1, "supervisor_decision": "stop"})

    def test_non_verbose_does_not_call_print_verbose_output(self) -> None:
        events = [
            {"supervisor": {"iteration": 1, "supervisor_decision": "stop"}},
        ]
        graph = self._make_graph(events)
        with patch("darwin.cli._print_verbose_output") as mock_print_verbose:
            _stream_with_progress(graph, {}, {}, max_iterations=3, verbose=False)
        mock_print_verbose.assert_not_called()

    def test_internal_events_skipped(self) -> None:
        events = [
            {"__start__": {}},
            {"supervisor": {"iteration": 1, "supervisor_decision": "stop"}},
        ]
        graph = self._make_graph(events)
        with patch("darwin.cli._print_verbose_output") as mock_print_verbose:
            _stream_with_progress(graph, {}, {}, max_iterations=3, verbose=True)
        # __start__ should be skipped; only supervisor should trigger verbose output
        mock_print_verbose.assert_called_once()
        assert mock_print_verbose.call_args[0][0] == "supervisor"


class TestMainVerboseArg:
    def test_verbose_flag_accepted(self) -> None:
        """--verbose flag should be accepted by the CLI parser without error."""
        with patch("sys.argv", ["darwin", "test topic", "--verbose"]):
            with patch("darwin.cli._stream_with_progress") as mock_stream:
                mock_stream.return_value = None
                with patch("darwin.graph.build_graph") as mock_build:
                    mock_graph = MagicMock()
                    mock_graph.stream.return_value = iter([])
                    mock_graph.get_state.return_value = MagicMock(
                        tasks=[], values={"final_hypotheses": [], "meta_review_notes": ""}
                    )
                    mock_build.return_value = mock_graph
                    with patch("darwin.review.display_final_results"):
                        main()
        mock_stream.assert_called_once()
        _, kwargs = mock_stream.call_args
        assert kwargs.get("verbose") is True

    def test_verbose_short_flag_accepted(self) -> None:
        """-v short flag should be accepted by the CLI parser without error."""
        with patch("sys.argv", ["darwin", "test topic", "-v"]):
            with patch("darwin.cli._stream_with_progress") as mock_stream:
                mock_stream.return_value = None
                with patch("darwin.graph.build_graph") as mock_build:
                    mock_graph = MagicMock()
                    mock_graph.stream.return_value = iter([])
                    mock_graph.get_state.return_value = MagicMock(
                        tasks=[], values={"final_hypotheses": [], "meta_review_notes": ""}
                    )
                    mock_build.return_value = mock_graph
                    with patch("darwin.review.display_final_results"):
                        main()
        mock_stream.assert_called_once()
        _, kwargs = mock_stream.call_args
        assert kwargs.get("verbose") is True

    def test_default_verbose_is_false(self) -> None:
        """verbose should default to False when flag is not provided."""
        with patch("sys.argv", ["darwin", "test topic"]):
            with patch("darwin.cli._stream_with_progress") as mock_stream:
                mock_stream.return_value = None
                with patch("darwin.graph.build_graph") as mock_build:
                    mock_graph = MagicMock()
                    mock_graph.stream.return_value = iter([])
                    mock_graph.get_state.return_value = MagicMock(
                        tasks=[], values={"final_hypotheses": [], "meta_review_notes": ""}
                    )
                    mock_build.return_value = mock_graph
                    with patch("darwin.review.display_final_results"):
                        main()
        mock_stream.assert_called_once()
        _, kwargs = mock_stream.call_args
        assert kwargs.get("verbose") is False
