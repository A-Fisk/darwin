"""Output generation — BibTeX and LaTeX from final hypotheses."""
from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path


def bibtex_key(paper: dict[str, str], used_keys: set[str] | None = None) -> str:
    """Generate a BibTeX key in the form {firstauthorlastname}{year}.

    Handles collisions by appending 'a', 'b', 'c', ... suffixes.
    """
    authors = paper.get("authors", "")
    year = str(paper.get("year", ""))

    # Extract first author's last name
    first_author = authors.split(",")[0].strip() if authors else ""
    if not first_author and authors:
        first_author = authors.split(" and ")[0].strip()

    # Take last word as surname
    parts = first_author.split()
    surname = parts[-1] if parts else "Unknown"

    # Sanitise: keep only ASCII alphanumeric
    surname = re.sub(r"[^a-zA-Z0-9]", "", surname)
    if not surname:
        surname = "Unknown"

    base_key = f"{surname}{year}" if year else surname

    if used_keys is None:
        return base_key

    if base_key not in used_keys:
        used_keys.add(base_key)
        return base_key

    # Collision: append a/b/c suffixes
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        candidate = f"{base_key}{suffix}"
        if candidate not in used_keys:
            used_keys.add(candidate)
            return candidate

    # Fallback with numeric suffix (extremely unlikely)
    for i in range(100):
        candidate = f"{base_key}{i}"
        if candidate not in used_keys:
            used_keys.add(candidate)
            return candidate

    return base_key  # give up deduplication


def generate_bibtex(literature_context: list[dict[str, str]]) -> str:
    """Generate a full .bib file from the literature context."""
    used_keys: set[str] = set()
    entries: list[str] = []

    for paper in literature_context:
        key = bibtex_key(paper, used_keys)
        title = paper.get("title", "")
        authors = paper.get("authors", "")
        year = str(paper.get("year", ""))
        venue = paper.get("venue", "")
        doi = paper.get("doi", "")
        url = paper.get("url", "")

        lines = [f"@article{{{key},"]
        if authors:
            lines.append(f"  author  = {{{authors}}},")
        if title:
            lines.append(f"  title   = {{{title}}},")
        if year:
            lines.append(f"  year    = {{{year}}},")
        if venue:
            lines.append(f"  journal = {{{venue}}},")
        if doi:
            lines.append(f"  doi     = {{{doi}}},")
        if url:
            lines.append(f"  url     = {{{url}}},")
        lines.append("}")

        entries.append("\n".join(lines))

    return "\n\n".join(entries) + "\n" if entries else ""


def _build_paper_index(
    literature_context: list[dict[str, str]],
) -> tuple[dict[str, str], list[str]]:
    """Return (paper_id -> bibtex_key, list of bibtex_keys in order)."""
    used_keys: set[str] = set()
    id_to_key: dict[str, str] = {}
    ordered_keys: list[str] = []
    for paper in literature_context:
        key = bibtex_key(paper, used_keys)
        pid = paper.get("paper_id", "")
        id_to_key[pid] = key
        ordered_keys.append(key)
    return id_to_key, ordered_keys


def _tex_escape(text: str) -> str:
    """Minimal LaTeX escaping for plain text content."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for char, repl in replacements:
        if char == "\\":
            # Must be done first to avoid double-escaping
            text = text.replace(char, repl)
        else:
            text = text.replace(char, repl)
    return text


def generate_latex(
    hypotheses: list[dict],
    literature_context: list[dict[str, str]],
    topic: str,
    meta_review_notes: str,
) -> str:
    """Generate a full .tex document using natbib citations."""
    id_to_key, _ = _build_paper_index(literature_context)

    lines: list[str] = []

    # Preamble
    lines += [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{natbib}",
        r"\usepackage{hyperref}",
        r"\usepackage{geometry}",
        r"\geometry{margin=1in}",
        r"\usepackage{parskip}",
        "",
        rf"\title{{Research Hypotheses: {_tex_escape(topic)}}}",
        r"\date{}",
        "",
        r"\begin{document}",
        r"\maketitle",
        "",
    ]

    # Hypothesis sections
    for i, hyp in enumerate(hypotheses, start=1):
        text: str = hyp.get("text", "")
        score: float = hyp.get("score", 0.0)
        generation: int = hyp.get("generation", 0)
        evolved_from: str | None = hyp.get("evolved_from")
        refs: list[str] = hyp.get("references", [])

        lines.append(rf"\section{{Hypothesis {i}}}")
        lines.append("")
        lines.append(_tex_escape(text))
        lines.append("")

        # Metadata
        lines.append(r"\textbf{Score:} " + f"{score:.2f}\\\\")
        lineage = f"Generation {generation}"
        if evolved_from:
            lineage += f" (evolved from {_tex_escape(evolved_from)})"
        lines.append(r"\textbf{Lineage:} " + _tex_escape(lineage) + r"\\")

        # Citations
        cite_keys = [id_to_key[pid] for pid in refs if pid in id_to_key]
        if cite_keys:
            cite_list = ",".join(cite_keys)
            lines.append(r"\textbf{References:} \citep{" + cite_list + r"}\\")

        lines.append("")

    # Meta-review section
    if meta_review_notes:
        lines += [
            r"\section{Meta-Review}",
            "",
            _tex_escape(meta_review_notes),
            "",
        ]

    # Bibliography
    lines += [
        r"\bibliographystyle{plainnat}",
        r"\bibliography{references}",
        "",
        r"\end{document}",
    ]

    return "\n".join(lines) + "\n"


def write_output(
    output_dir: str | os.PathLike,
    hypotheses: list[dict],
    literature_context: list[dict[str, str]],
    topic: str,
    meta_review_notes: str,
) -> None:
    """Write hypotheses.tex and references.bib to output_dir."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    tex = generate_latex(hypotheses, literature_context, topic, meta_review_notes)
    bib = generate_bibtex(literature_context)

    (out / "hypotheses.tex").write_text(tex, encoding="utf-8")
    (out / "references.bib").write_text(bib, encoding="utf-8")
