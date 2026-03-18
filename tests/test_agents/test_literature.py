"""Tests for the literature agent."""
from unittest.mock import MagicMock, patch

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
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {
                "paperId": "id1",
                "title": "Paper One",
                "abstract": "Abstract one.",
                "authors": [{"name": "Alice"}],
                "url": "https://example.com/1",
            },
        ]
    }

    with patch("darwin.agents.literature.httpx.get", return_value=mock_response):
        result = run(_make_state())  # type: ignore[arg-type]

    papers = result.get("literature_context", [])
    assert len(papers) == 1  # type: ignore[arg-type]
    assert papers[0]["paper_id"] == "id1"  # type: ignore[index]
    assert papers[0]["title"] == "Paper One"  # type: ignore[index]


def test_run_handles_network_error_gracefully() -> None:
    """Agent returns empty context on network failure, does not raise."""
    import httpx

    with patch("darwin.agents.literature.httpx.get", side_effect=httpx.HTTPError("timeout")):
        result = run(_make_state())  # type: ignore[arg-type]

    papers = result.get("literature_context", [])
    assert papers == []  # type: ignore[comparison-overlap]
