"""Literature agent — fetches relevant papers from Semantic Scholar."""
from __future__ import annotations

import httpx

from darwin.state import ResearchState

_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_TOP_N = 10
_FIELDS = "title,abstract,authors,url,paperId"


def run(state: ResearchState) -> dict[str, object]:
    """Fetch top N papers from Semantic Scholar for the research topic.

    Runs only on the first iteration (literature_context empty). Subsequent
    iterations reuse the cached results to avoid redundant API calls.
    """
    # Skip if we already have literature context
    if state.get("literature_context"):
        return {
            "messages": [
                {
                    "role": "agent",
                    "agent": "literature",
                    "content": (
                        f"literature_context already populated "
                        f"({len(state['literature_context'])} papers)"
                    ),
                }
            ]
        }

    topic = state["topic"]
    papers: list[dict[str, str]] = []

    try:
        response = httpx.get(
            _API_URL,
            params={"query": topic, "limit": _TOP_N, "fields": _FIELDS},
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()

        for item in data.get("data", []):
            abstract = item.get("abstract") or ""
            authors_raw = item.get("authors") or []
            authors = ", ".join(a.get("name", "") for a in authors_raw)
            papers.append(
                {
                    "paper_id": item.get("paperId", ""),
                    "title": item.get("title", ""),
                    "abstract": abstract[:600],  # Truncate long abstracts
                    "authors": authors,
                    "url": (
                        item.get("url")
                        or f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}"
                    ),
                }
            )
    except httpx.HTTPError:
        # Network failure — continue without literature context rather than crashing
        papers = []

    return {
        "literature_context": papers,
        "messages": [
            {
                "role": "agent",
                "agent": "literature",
                "content": f"fetched {len(papers)} papers for topic: {topic!r}",
            }
        ],
    }
