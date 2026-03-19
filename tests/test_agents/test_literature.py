"""Tests for the literature agent."""
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from darwin.agents.literature import run


def _make_state(topic: str = "test topic", lit_context: list | None = None) -> dict:  # type: ignore[type-arg]
    return {
        "topic": topic,
        "literature_context": lit_context if lit_context is not None else [],
        "hypotheses": [],
        "iteration": 1,
        "max_iterations": 5,
        "ranked_ids": [],
        "top_hypotheses": [],
        "proximity_clusters": [],
        "supervisor_decision": "continue",
        "meta_review_notes": "",
        "human_feedback": None,
        "final_hypotheses": [],
        "messages": [],
    }


def _make_ok_response(data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"data": data or []}
    return mock


def test_run_skips_if_context_populated() -> None:
    """Agent is a no-op if literature_context already has papers."""
    existing = [{"paper_id": "abc", "title": "A Paper", "abstract": "", "authors": "", "url": ""}]
    state = _make_state(lit_context=existing)
    result = run(state)  # type: ignore[arg-type]
    assert "literature_context" not in result
    msgs = result.get("messages", [])
    assert any("already populated" in str(m.get("content", "")) for m in msgs)  # type: ignore[union-attr]


def test_run_fetches_papers_on_empty_context() -> None:
    """Agent fetches papers when literature_context is empty."""
    mock_response = _make_ok_response(
        data=[
            {
                "paperId": "id1",
                "title": "Paper One",
                "abstract": "Abstract one.",
                "authors": [{"name": "Alice"}],
                "url": "https://example.com/1",
            },
        ]
    )

    with patch("darwin.agents.literature.httpx.get", return_value=mock_response):
        result = run(_make_state())  # type: ignore[arg-type]

    papers = result.get("literature_context", [])
    assert len(papers) == 1  # type: ignore[arg-type]
    assert papers[0]["paper_id"] == "id1"  # type: ignore[index]
    assert papers[0]["title"] == "Paper One"  # type: ignore[index]


def test_run_handles_network_error_gracefully() -> None:
    """Agent returns empty context on network failure after retries, does not raise."""
    with (
        patch("darwin.agents.literature.httpx.get", side_effect=httpx.HTTPError("timeout")),
        patch("darwin.agents.literature.time.sleep"),
    ):
        result = run(_make_state())  # type: ignore[arg-type]

    papers = result.get("literature_context", [])
    assert papers == []  # type: ignore[comparison-overlap]
    msgs = result.get("messages", [])
    assert any("error" in str(m.get("content", "")) for m in msgs)


def test_run_retries_on_429_then_succeeds() -> None:
    """Agent retries on 429 and succeeds on next attempt."""
    rate_limited = MagicMock()
    rate_limited.status_code = 429

    ok_response = _make_ok_response(
        data=[{"paperId": "id2", "title": "Retry Paper", "abstract": "", "authors": [], "url": ""}]
    )

    with (
        patch(
            "darwin.agents.literature.httpx.get",
            side_effect=[rate_limited, ok_response],
        ),
        patch("darwin.agents.literature.time.sleep") as mock_sleep,
    ):
        result = run(_make_state())  # type: ignore[arg-type]

    assert mock_sleep.call_count == 1
    papers = result.get("literature_context", [])
    assert len(papers) == 1  # type: ignore[arg-type]
    assert papers[0]["paper_id"] == "id2"  # type: ignore[index]


def test_run_retries_on_500_then_fails() -> None:
    """Agent retries on 5xx and surfaces error after all retries exhausted."""
    server_error = MagicMock()
    server_error.status_code = 503
    server_error.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503", request=MagicMock(), response=server_error
    )

    with (
        patch("darwin.agents.literature.httpx.get", return_value=server_error),
        patch("darwin.agents.literature.time.sleep") as mock_sleep,
    ):
        result = run(_make_state())  # type: ignore[arg-type]

    # 3 retries → 3 sleeps
    assert mock_sleep.call_count == 3
    papers = result.get("literature_context", [])
    assert papers == []  # type: ignore[comparison-overlap]
    msgs = result.get("messages", [])
    assert any("error" in str(m.get("content", "")) for m in msgs)
