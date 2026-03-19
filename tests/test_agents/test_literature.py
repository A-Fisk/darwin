"""Tests for the literature agent."""
from unittest.mock import MagicMock, patch

import httpx

from darwin.agents.literature import _fetch_arxiv, _fetch_pubmed, run


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


def _make_ss_response(data: list | None = None) -> MagicMock:
    """Semantic Scholar success response."""
    return _make_ok_response(data)


def _make_pubmed_search_response(ids: list[str]) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.json.return_value = {"esearchresult": {"idlist": ids}}
    return mock


def _make_pubmed_summary_response(ids: list[str]) -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    result: dict = {"uids": ids}
    for pmid in ids:
        result[pmid] = {
            "uid": pmid,
            "title": f"PubMed Paper {pmid}",
            "authors": [{"name": "Author A"}],
            "pubdate": "2023 Jan",
            "source": "Nature",
            "articleids": [{"idtype": "doi", "value": f"10.1234/{pmid}"}],
        }
    mock.json.return_value = {"result": result}
    return mock


_ARXIV_ATOM = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.00001v1</id>
    <title>arXiv Paper One</title>
    <summary>Abstract of arXiv paper one.</summary>
    <author><name>Author B</name></author>
    <published>2023-01-15T00:00:00Z</published>
  </entry>
</feed>
"""


def _make_arxiv_response() -> MagicMock:
    mock = MagicMock()
    mock.status_code = 200
    mock.raise_for_status = MagicMock()
    mock.text = _ARXIV_ATOM
    return mock


def _make_http_error_response(status: int) -> MagicMock:
    mock = MagicMock()
    mock.status_code = status
    mock.raise_for_status.side_effect = httpx.HTTPStatusError(
        str(status), request=MagicMock(), response=mock
    )
    return mock


# ---------------------------------------------------------------------------
# Existing behaviour tests
# ---------------------------------------------------------------------------


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
    msgs = result.get("messages", [])
    assert any("semantic_scholar" in str(m.get("content", "")) for m in msgs)


def test_run_handles_network_error_gracefully() -> None:
    """Agent returns empty context when all fallbacks fail, does not raise."""
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
    """Agent retries on 5xx and falls back when all retries exhausted."""
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

    # 3 retries from Semantic Scholar → 3 sleeps
    assert mock_sleep.call_count == 3
    papers = result.get("literature_context", [])
    assert papers == []  # type: ignore[comparison-overlap]
    msgs = result.get("messages", [])
    assert any("error" in str(m.get("content", "")) for m in msgs)


# ---------------------------------------------------------------------------
# Fallback behaviour tests
# ---------------------------------------------------------------------------


def test_run_falls_back_to_pubmed_on_429() -> None:
    """Agent falls back to PubMed when Semantic Scholar returns 429 after retries."""
    rate_limited = _make_http_error_response(429)
    pubmed_search = _make_pubmed_search_response(["99999"])
    pubmed_summary = _make_pubmed_summary_response(["99999"])

    with (
        patch(
            "darwin.agents.literature.httpx.get",
            side_effect=[
                rate_limited,  # SS attempt 1
                rate_limited,  # SS attempt 2
                rate_limited,  # SS attempt 3
                rate_limited,  # SS attempt 4 (last retry → raises)
                pubmed_search,  # PubMed esearch
                pubmed_summary,  # PubMed esummary
            ],
        ),
        patch("darwin.agents.literature.time.sleep"),
    ):
        result = run(_make_state())  # type: ignore[arg-type]

    papers = result.get("literature_context", [])
    assert len(papers) == 1  # type: ignore[arg-type]
    assert papers[0]["paper_id"] == "99999"  # type: ignore[index]
    assert papers[0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/99999/"  # type: ignore[index]
    msgs = result.get("messages", [])
    assert any("pubmed" in str(m.get("content", "")) for m in msgs)


def test_run_falls_back_to_arxiv_when_pubmed_also_fails() -> None:
    """Agent falls back to arXiv when both SS and PubMed fail."""
    error = httpx.HTTPError("connection refused")
    arxiv_resp = _make_arxiv_response()

    with (
        patch(
            "darwin.agents.literature.httpx.get",
            side_effect=[
                error,  # SS attempt 1
                error,  # SS attempt 2
                error,  # SS attempt 3
                error,  # SS attempt 4
                error,  # PubMed esearch
                arxiv_resp,  # arXiv
            ],
        ),
        patch("darwin.agents.literature.time.sleep"),
    ):
        result = run(_make_state())  # type: ignore[arg-type]

    papers = result.get("literature_context", [])
    assert len(papers) == 1  # type: ignore[arg-type]
    assert papers[0]["paper_id"] == "2301.00001v1"  # type: ignore[index]
    assert papers[0]["venue"] == "arXiv"  # type: ignore[index]
    msgs = result.get("messages", [])
    assert any("arxiv" in str(m.get("content", "")) for m in msgs)


def test_run_message_includes_source_on_success() -> None:
    """Output message includes source name."""
    ok_response = _make_ok_response(
        data=[{"paperId": "x1", "title": "T", "abstract": "", "authors": [], "url": ""}]
    )
    with patch("darwin.agents.literature.httpx.get", return_value=ok_response):
        result = run(_make_state())  # type: ignore[arg-type]

    msgs = result.get("messages", [])
    content = str(msgs[0].get("content", ""))
    assert "from semantic_scholar" in content


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


def test_fetch_pubmed_normalises_schema() -> None:
    """_fetch_pubmed returns dicts with the expected keys."""
    pubmed_search = _make_pubmed_search_response(["11111"])
    pubmed_summary = _make_pubmed_summary_response(["11111"])

    with patch("darwin.agents.literature.httpx.get", side_effect=[pubmed_search, pubmed_summary]):
        papers = _fetch_pubmed("machine learning")

    assert len(papers) == 1
    p = papers[0]
    assert p["paper_id"] == "11111"
    assert p["title"] == "PubMed Paper 11111"
    assert p["authors"] == "Author A"
    assert p["year"] == "2023"
    assert p["venue"] == "Nature"
    assert p["doi"] == "10.1234/11111"
    assert p["url"] == "https://pubmed.ncbi.nlm.nih.gov/11111/"
    assert "abstract" in p


def test_fetch_pubmed_returns_empty_on_no_ids() -> None:
    """_fetch_pubmed returns [] when esearch finds no results."""
    empty_search = _make_pubmed_search_response([])

    with patch("darwin.agents.literature.httpx.get", return_value=empty_search):
        papers = _fetch_pubmed("xyzzy irrelevant")

    assert papers == []


def test_fetch_arxiv_normalises_schema() -> None:
    """_fetch_arxiv returns dicts with the expected keys."""
    arxiv_resp = _make_arxiv_response()

    with patch("darwin.agents.literature.httpx.get", return_value=arxiv_resp):
        papers = _fetch_arxiv("neural networks")

    assert len(papers) == 1
    p = papers[0]
    assert p["paper_id"] == "2301.00001v1"
    assert p["title"] == "arXiv Paper One"
    assert "Abstract" in p["abstract"]
    assert p["authors"] == "Author B"
    assert p["year"] == "2023"
    assert p["venue"] == "arXiv"
    assert p["url"] == "https://arxiv.org/abs/2301.00001v1"
    assert "abstract" in p
