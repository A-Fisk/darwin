"""Output generation — BibTeX, LaTeX, and text from final hypotheses."""
from __future__ import annotations

import os
import re
import textwrap
from datetime import datetime
from pathlib import Path


def _extract_topic_keywords(title: str, max_keywords: int = 2) -> list[str]:
    """Extract meaningful keywords from paper title for BibTeX key."""
    if not title:
        return []

    # Common stop words to exclude
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "about", "into", "through", "during",
        "before", "after", "above", "below", "up", "down", "out", "off", "over",
        "under", "again", "further", "then", "once", "here", "there", "when",
        "where", "why", "how", "all", "any", "both", "each", "few", "more",
        "most", "other", "some", "such", "no", "nor", "not", "only", "own",
        "same", "so", "than", "too", "very", "can", "will", "just", "should",
        "now", "analysis", "study", "research", "approach", "method", "model",
        "system", "using", "based", "novel", "new", "improved", "enhanced",
        "towards", "via", "framework", "application", "applications"
    }

    # Clean and split title
    title_clean = re.sub(r"[^\w\s-]", "", title.lower())
    words = [w.strip() for w in title_clean.split() if len(w.strip()) >= 3]

    # Filter keywords: not stop words, reasonable length, contains letters
    keywords = []
    for word in words:
        if (word not in stop_words
            and len(word) >= 3
            and re.search(r"[a-z]", word)
            and not word.isdigit()):
            keywords.append(word)
        if len(keywords) >= max_keywords:
            break

    return keywords[:max_keywords]


def _format_author_component(authors: str) -> str:
    """Format author names for BibTeX key using better-bibtex style."""
    if not authors:
        return "unknown"

    # Normalize separators and split
    authors_normalized = authors.replace(" and ", ", ").replace(";", ",").replace("&", ",")

    # Split by commas and clean
    parts = [p.strip() for p in authors_normalized.split(",") if p.strip()]

    # Determine how many actual authors we have
    # Common patterns:
    # "Smith, John" -> 1 author
    # "Smith, John, Doe, Jane" -> 2 authors (LastName, FirstName pairs)
    # "Smith John Doe Jane" -> could be 2 or 4 authors, tricky
    # "Smith and Doe" -> 2 authors (already normalized above)

    author_surnames = []

    if len(parts) == 1:
        # Single name or "FirstName LastName" format
        name_parts = parts[0].split()
        if len(name_parts) >= 2:
            # "FirstName LastName" -> use LastName
            surname = name_parts[-1]
        else:
            # Single name
            surname = parts[0]
        author_surnames.append(surname)

    elif len(parts) == 2:
        # Could be "LastName, FirstName" (1 author) or "Author1, Author2" (2 authors)
        # Check if second part looks like a first name (no spaces, common first names)
        second_part = parts[1].strip()
        if len(second_part.split()) == 1:
            # Likely "LastName, FirstName" format - single author
            surname = parts[0].strip()
            author_surnames.append(surname)
        else:
            # Likely two separate authors
            for part in parts:
                name_parts = part.strip().split()
                surname = name_parts[-1] if name_parts else part
                author_surnames.append(surname)

    elif len(parts) % 2 == 0 and len(parts) > 2:
        # Even number > 2, assume "LastName, FirstName" pairs
        for i in range(0, len(parts), 2):
            surname = parts[i].strip()
            author_surnames.append(surname)

    else:
        # Odd number > 2 or other case - treat each comma-separated part as an author
        for part in parts:
            name_parts = part.strip().split()
            surname = name_parts[-1] if name_parts else part
            author_surnames.append(surname)

    # Clean surnames and limit to first 4
    clean_surnames = []
    for surname in author_surnames[:4]:
        surname_clean = re.sub(r"[^a-zA-Z0-9]", "", surname)
        if surname_clean:
            clean_surnames.append(surname_clean)

    if not clean_surnames:
        return "unknown"

    # Format based on number of authors
    if len(clean_surnames) == 1:
        return clean_surnames[0].lower()
    elif len(clean_surnames) == 2:
        return f"{clean_surnames[0].lower()}{clean_surnames[1].capitalize()}"
    else:  # 3 or more authors
        return f"{clean_surnames[0].lower()}EtAl"


def bibtex_key(paper: dict[str, str], used_keys: set[str] | None = None) -> str:
    """Generate a better-bibtex style BibTeX key with topic keywords and improved author handling.

    Format: {author_component}{year}{topic_keywords}
    Examples:
    - smith2023sleep
    - smithJones2023neuralNetworks
    - smithEtAl2023machineLearning

    Handles collisions by appending 'a', 'b', 'c', ... suffixes.
    """
    authors = paper.get("authors", "")
    year = str(paper.get("year", ""))
    title = paper.get("title", "")

    # Format author component
    author_component = _format_author_component(authors)

    # Extract topic keywords
    keywords = _extract_topic_keywords(title, max_keywords=2)
    topic_component = "".join(word.capitalize() for word in keywords)

    # Build base key: author + year + topic (camelCase)
    components = [author_component]
    if year:
        components.append(year)
    if topic_component:
        components.append(topic_component)

    base_key = "".join(components)

    # Ensure reasonable key length (truncate if too long)
    if len(base_key) > 50:
        # Keep author + year, truncate topic
        author_year = f"{author_component}{year}" if year else author_component
        max_topic_len = 50 - len(author_year)
        if max_topic_len > 0 and topic_component:
            topic_component = topic_component[:max_topic_len]
            base_key = f"{author_year}{topic_component}"
        else:
            base_key = author_year

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


def _add_inline_citations(
    hypothesis_text: str,
    references: list[str],
    id_to_key: dict[str, str],
    literature_context: list[dict[str, str]],
) -> str:
    """Add in-text citations to hypothesis text where claims are made.

    Analyzes the hypothesis text and inserts appropriate citations where
    evidence is likely referenced or claims are made.
    """
    if not references or not id_to_key:
        return _tex_escape(hypothesis_text)

    # Get available cite keys for this hypothesis
    cite_keys = [id_to_key[pid] for pid in references if pid in id_to_key]
    if not cite_keys:
        return _tex_escape(hypothesis_text)

    # Build a mapping of paper topics/keywords to cite keys
    paper_keywords = {}
    for paper in literature_context:
        if paper.get("paper_id") in references:
            key = id_to_key.get(paper.get("paper_id", ""))
            if key:
                # Extract keywords from title
                title_words = paper.get("title", "").lower().split()
                for word in title_words:
                    # Clean word and add to mapping
                    clean_word = re.sub(r'[^\w]', '', word)
                    if len(clean_word) > 3:  # Only meaningful words
                        paper_keywords[clean_word] = key

    # Split hypothesis into sentences
    sentences = re.split(r'(?<=[.!?])\s+', hypothesis_text.strip())
    processed_sentences = []

    for sentence in sentences:
        if not sentence.strip():
            continue

        # Check if sentence contains claims that warrant citation
        sentence_lower = sentence.lower()

        # Heuristics for where to add citations:
        claim_indicators = [
            r'\b(recent|studies?|research|findings?|evidence|shows?|demonstrates?|indicates?|suggests?|reports?)\b',
            r'\b(advances?|developments?|improvements?|breakthroughs?)\b',
            r'\b(according to|based on|as shown)\b',
            r'\b(machine learning|deep learning|neural networks?|algorithms?)\b',
            r'\b(protein folding|prediction|accuracy|performance)\b',
        ]

        has_claim = any(re.search(pattern, sentence_lower) for pattern in claim_indicators)

        # Try to match sentence content with paper keywords
        best_cite_key = None
        best_match_score = 0
        for keyword, key in paper_keywords.items():
            if keyword in sentence_lower:
                # Score based on keyword length and specificity
                match_score = len(keyword)
                if match_score > best_match_score:
                    best_match_score = match_score
                    best_cite_key = key

        # If no specific match, use first available citation for claimed sentences
        if has_claim and not best_cite_key and cite_keys:
            best_cite_key = cite_keys[0]

        # Add citation to sentence if warranted
        if best_cite_key and has_claim:
            # Find a good spot to insert citation (end of sentence is safe)
            sentence = sentence.rstrip()
            if sentence.endswith('.'):
                sentence = sentence[:-1] + f" CITATIONMARK{best_cite_key}CITATIONMARK."
            else:
                sentence = sentence + f" CITATIONMARK{best_cite_key}CITATIONMARK"

        processed_sentences.append(sentence)

    # Escape the text first, then replace citation markers with actual LaTeX commands
    result = _tex_escape(" ".join(processed_sentences))

    # Now replace the citation markers with proper LaTeX commands
    # This avoids having the citation commands themselves escaped
    result = re.sub(r'CITATIONMARK(\w+)CITATIONMARK', r'\\citep{\1}', result)

    return result


def generate_latex(
    hypotheses: list[dict[str, object]],
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
        # Add in-text citations to the hypothesis text
        text_with_citations = _add_inline_citations(text, refs, id_to_key, literature_context)
        lines.append(text_with_citations)
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


def generate_text_output(
    hypotheses: list[dict[str, object]],
    literature_context: list[dict[str, str]],
    topic: str,
    meta_review_notes: str,
    max_iterations: int | None = None,
) -> str:
    """Generate human-readable text output with ranked hypotheses and references."""
    lines = []

    # Header with timestamp and parameters
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.extend([
        "=" * 80,
        "DARWIN CO-SCIENTIST RESEARCH RESULTS",
        "=" * 80,
        "",
        f"Topic: {topic}",
        f"Generated: {timestamp}",
        f"Max iterations: {max_iterations or 'N/A'}",
        f"Total hypotheses: {len(hypotheses)}",
        "",
    ])

    # Final ranked hypotheses
    lines.extend([
        "FINAL RANKED HYPOTHESES",
        "-" * 40,
        "",
    ])

    if not hypotheses:
        lines.append("No hypotheses generated.")
    else:
        for rank, hyp in enumerate(hypotheses, 1):
            text: str = hyp.get("text", "")
            score: float = hyp.get("score", 0.0)
            generation: int = hyp.get("generation", 0)
            evolved_from: str | None = hyp.get("evolved_from")
            refs: list[str] = hyp.get("references", [])

            lines.extend([
                f"#{rank}. [Score: {score:.4f}]",
                "",
                # Wrap the hypothesis text nicely
                *textwrap.wrap(text, width=76, initial_indent="   ", subsequent_indent="   "),
                "",
                f"   Generation: {generation}",
            ])

            if evolved_from:
                lines.append(f"   Evolved from: {evolved_from}")

            # Add reference information
            if refs:
                ref_papers = [p for p in literature_context if p.get("paper_id") in refs]
                if ref_papers:
                    lines.append("   References:")
                    for paper in ref_papers:
                        title = paper.get("title", "Unknown title")
                        authors = paper.get("authors", "Unknown authors")
                        year = paper.get("year", "Unknown year")
                        venue = paper.get("venue", "")

                        # Format: Authors (Year). Title. Venue.
                        citation = f"     • {authors} ({year}). {title}."
                        if venue:
                            citation += f" {venue}."

                        # Wrap long citations
                        wrapped = textwrap.wrap(citation, width=76,
                                              initial_indent="",
                                              subsequent_indent="       ")
                        lines.extend(wrapped)

            lines.append("")  # Blank line after each hypothesis

    # Meta-review section
    if meta_review_notes:
        lines.extend([
            "",
            "META-REVIEW SUMMARY",
            "-" * 40,
            "",
        ])
        # Wrap meta-review notes
        wrapped_notes = textwrap.wrap(meta_review_notes, width=76)
        lines.extend(wrapped_notes)
        lines.append("")

    # Literature sources used
    if literature_context:
        lines.extend([
            "",
            "LITERATURE SOURCES",
            "-" * 40,
            "",
            f"Total papers referenced: {len(literature_context)}",
            "",
        ])

        for i, paper in enumerate(literature_context, 1):
            title = paper.get("title", "Unknown title")
            authors = paper.get("authors", "Unknown authors")
            year = paper.get("year", "Unknown year")
            venue = paper.get("venue", "")
            doi = paper.get("doi", "")
            url = paper.get("url", "")

            lines.append(f"{i}. {authors} ({year}). {title}.")
            if venue:
                lines.append(f"   Published in: {venue}")
            if doi:
                lines.append(f"   DOI: {doi}")
            if url:
                lines.append(f"   URL: {url}")
            lines.append("")

    # Footer
    lines.extend([
        "",
        "=" * 80,
        f"Generated by Darwin Co-Scientist on {timestamp}",
        "=" * 80,
    ])

    return "\n".join(lines) + "\n"


def write_text_output(
    output_file: str | os.PathLike[str],
    hypotheses: list[dict[str, object]],
    literature_context: list[dict[str, str]],
    topic: str,
    meta_review_notes: str,
    max_iterations: int | None = None,
) -> None:
    """Write human-readable text output to a specified file."""
    text_content = generate_text_output(
        hypotheses=hypotheses,
        literature_context=literature_context,
        topic=topic,
        meta_review_notes=meta_review_notes,
        max_iterations=max_iterations,
    )

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text_content, encoding="utf-8")


def write_output(
    output_dir: str | os.PathLike[str],
    hypotheses: list[dict[str, object]],
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
