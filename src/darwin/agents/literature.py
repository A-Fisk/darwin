"""Literature agent — fetches relevant papers from Semantic Scholar."""
from __future__ import annotations

import random
import time

import anthropic
import httpx

from darwin.state import ResearchState

_API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_TOP_N = 10
_FIELDS = "title,abstract,authors,year,venue,externalIds,url,paperId"


def _distil_query(topic: str) -> str:
    """Use Claude to distil a verbose research topic into 2-4 search keywords."""
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=64,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Convert this research topic into 2-4 concise keywords suitable "
                    f"for a Semantic Scholar search query. Output ONLY the keywords, "
                    f"nothing else.\n\nTopic: {topic}"
                ),
            }
        ],
    )
    return message.content[0].text.strip()


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
    query = _distil_query(topic)
    papers: list[dict[str, str]] = []

    _MAX_RETRIES = 3
    _BASE_DELAY = 1.0  # seconds

    response = None
    fetch_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        fetch_exc = None
        try:
            response = httpx.get(
                _API_URL,
                params={"query": query, "limit": _TOP_N, "fields": _FIELDS},
                timeout=15.0,
            )
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2**attempt) + random.uniform(0, 0.5)
                    time.sleep(delay)
                    continue
                response.raise_for_status()
            response.raise_for_status()
            break  # success
        except httpx.HTTPError as exc:
            fetch_exc = exc
            if attempt < _MAX_RETRIES:
                delay = _BASE_DELAY * (2**attempt) + random.uniform(0, 0.5)
                time.sleep(delay)

    try:
        if fetch_exc is not None:
            raise fetch_exc
        if response is None:
            raise RuntimeError("No response received")
        data = response.json()

        for item in data.get("data", []):
            abstract = item.get("abstract") or ""
            authors_raw = item.get("authors") or []
            authors = ", ".join(a.get("name", "") for a in authors_raw)
            external_ids = item.get("externalIds") or {}
            doi = external_ids.get("DOI", "")
            papers.append(
                {
                    "paper_id": item.get("paperId", ""),
                    "title": item.get("title", ""),
                    "abstract": abstract[:600],  # Truncate long abstracts
                    "authors": authors,
                    "year": item.get("year") or "",
                    "venue": item.get("venue") or "",
                    "doi": doi,
                    "url": (
                        item.get("url")
                        or f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}"
                    ),
                }
            )
    except httpx.HTTPError as exc:
        # Network/HTTP failure (incl. 429 rate limit) — continue without literature context
        papers = []
        error_note = str(exc)
    except Exception as exc:
        # JSON decode error or other unexpected failure
        papers = []
        error_note = str(exc)
    else:
        error_note = ""

    error_suffix = f"; error: {error_note}" if error_note else ""
    return {
        "literature_context": papers,
        "messages": [
            {
                "role": "agent",
                "agent": "literature",
                "content": f"fetched {len(papers)} papers (query: {query!r}){error_suffix}",
            }
        ],
    }
