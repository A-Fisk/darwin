"""Literature agent — fetches relevant papers from Semantic Scholar with PubMed/arXiv fallbacks."""
from __future__ import annotations

import random
import time
import xml.etree.ElementTree as ET

import anthropic
import httpx

from darwin.config import MAX_TOKENS_SIMPLE
from darwin.console import progress_context
from darwin.state import ResearchState

_SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_PUBMED_SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_PUBMED_SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_ARXIV_URL = "http://export.arxiv.org/api/query"
_TOP_N = 10
_FIELDS = "title,abstract,authors,year,venue,externalIds,url,paperId"
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds


def _distil_query(topic: str) -> str:
    """Use Claude to distil a verbose research topic into 2-4 search keywords."""
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=MAX_TOKENS_SIMPLE,
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


def _fetch_semantic_scholar(query: str) -> list[dict[str, str]]:
    """Fetch papers from Semantic Scholar. Raises on 429/network failure after retries."""
    response = None
    fetch_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        fetch_exc = None
        try:
            response = httpx.get(
                _SEMANTIC_SCHOLAR_URL,
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

    if fetch_exc is not None:
        raise fetch_exc
    if response is None:
        raise RuntimeError("No response received")

    data = response.json()
    papers: list[dict[str, str]] = []
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
                "abstract": abstract[:600],
                "authors": authors,
                "year": str(item.get("year") or ""),
                "venue": item.get("venue") or "",
                "doi": doi,
                "url": (
                    item.get("url")
                    or f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}"
                ),
            }
        )
    return papers


def _fetch_pubmed(query: str) -> list[dict[str, str]]:
    """Fetch papers from PubMed E-utilities API. Raises on HTTP failure."""
    search_resp = httpx.get(
        _PUBMED_SEARCH_URL,
        params={"db": "pubmed", "term": query, "retmax": _TOP_N, "retmode": "json"},
        timeout=15.0,
    )
    search_resp.raise_for_status()
    ids: list[str] = search_resp.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []

    summary_resp = httpx.get(
        _PUBMED_SUMMARY_URL,
        params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"},
        timeout=15.0,
    )
    summary_resp.raise_for_status()
    result = summary_resp.json().get("result", {})

    papers: list[dict[str, str]] = []
    for pmid in ids:
        item = result.get(pmid)
        if not item or not isinstance(item, dict):
            continue
        authors_raw = item.get("authors", [])
        authors = ", ".join(a.get("name", "") for a in authors_raw[:5])
        pubdate = item.get("pubdate", "")
        year = pubdate[:4] if pubdate else ""
        doi = ""
        for aid in item.get("articleids", []):
            if aid.get("idtype") == "doi":
                doi = aid.get("value", "")
                break
        papers.append(
            {
                "paper_id": pmid,
                "title": item.get("title", ""),
                "abstract": "",
                "authors": authors,
                "year": year,
                "venue": item.get("source", ""),
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
        )
    return papers


def _fetch_arxiv(query: str) -> list[dict[str, str]]:
    """Fetch papers from arXiv API. Raises on HTTP failure."""
    resp = httpx.get(
        _ARXIV_URL,
        params={"search_query": f"all:{query}", "max_results": _TOP_N},
        timeout=15.0,
    )
    resp.raise_for_status()

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)

    papers: list[dict[str, str]] = []
    for entry in root.findall("atom:entry", ns):
        arxiv_id_url = entry.findtext("atom:id", "", ns)
        arxiv_id = arxiv_id_url.split("/abs/")[-1] if "/abs/" in arxiv_id_url else arxiv_id_url

        title_el = entry.find("atom:title", ns)
        title = " ".join((title_el.text or "").split()) if title_el is not None else ""

        abstract_el = entry.find("atom:summary", ns)
        abstract = " ".join((abstract_el.text or "").split()) if abstract_el is not None else ""

        authors = ", ".join(
            (a.findtext("atom:name", "", ns) or "")
            for a in entry.findall("atom:author", ns)[:5]
        )

        published = entry.findtext("atom:published", "", ns)
        year = published[:4] if published else ""

        doi = ""
        for link in entry.findall("atom:link", ns):
            if link.get("title") == "doi":
                href = link.get("href", "")
                doi = href.replace("http://dx.doi.org/", "").replace("https://doi.org/", "")
                break

        papers.append(
            {
                "paper_id": arxiv_id,
                "title": title,
                "abstract": abstract[:600],
                "authors": authors,
                "year": year,
                "venue": "arXiv",
                "doi": doi,
                "url": f"https://arxiv.org/abs/{arxiv_id}",
            }
        )
    return papers


def run(state: ResearchState) -> dict[str, object]:
    """Fetch top N papers for the research topic.

    Tries Semantic Scholar first; falls back to PubMed then arXiv on 429 or
    persistent failure. Runs only on the first iteration (literature_context
    empty). Subsequent iterations reuse the cached results.
    """
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

    with progress_context(f"Fetching literature for research topic") as progress:
        task = progress.add_task(f"[cyan]Fetching papers", total=1)

        progress.update(task, advance=0, description=f"[cyan]Distilling search query from topic...")
        query = _distil_query(topic)

        papers: list[dict[str, str]] | None = None
        source = "semantic_scholar"
        error_note = ""

        # Attempt 1: Semantic Scholar
        progress.update(task, advance=0.2, description=f"[cyan]Searching Semantic Scholar...")
        try:
            papers = _fetch_semantic_scholar(query)
            source = "semantic_scholar"
        except Exception as exc:
            error_note = str(exc)

        # Fallback 1: PubMed
        if papers is None:
            progress.update(task, advance=0.4, description=f"[cyan]Semantic Scholar failed, trying PubMed...")
            try:
                papers = _fetch_pubmed(query)
                source = "pubmed"
                error_note = ""
            except Exception as exc:
                error_note = str(exc)

        # Fallback 2: arXiv
        if papers is None:
            progress.update(task, advance=0.7, description=f"[cyan]PubMed failed, trying arXiv...")
            try:
                papers = _fetch_arxiv(query)
                source = "arxiv"
                error_note = ""
            except Exception as exc:
                error_note = str(exc)
                papers = []

        progress.update(task, advance=1.0, description=f"[cyan]Fetched {len(papers)} papers from {source}!")
        progress.update(task, completed=1)

    error_suffix = f"; error: {error_note}" if error_note else ""
    return {
        "literature_context": papers,
        "query": query,
        "messages": [
            {
                "role": "agent",
                "agent": "literature",
                "content": (
                    f"fetched {len(papers)} papers from {source} "
                    f"(query: {query!r}){error_suffix}"
                ),
            }
        ],
    }
