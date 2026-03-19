"""Tests for output.py — BibTeX and LaTeX generation."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from darwin.output import (
    bibtex_key,
    generate_bibtex,
    generate_latex,
    generate_text_output,
    write_output,
    write_text_output,
)

_PAPER_1 = {
    "paper_id": "abc123",
    "title": "Deep Learning for Protein Folding",
    "authors": "Smith, John, Doe, Jane",
    "year": "2022",
    "venue": "Nature",
    "doi": "10.1234/nature.2022",
    "url": "https://example.com/paper1",
}

_PAPER_2 = {
    "paper_id": "def456",
    "title": "Transformer Architecture Advances",
    "authors": "Johnson, Alice, Lee, Bob",
    "year": "2023",
    "venue": "NeurIPS",
    "doi": "",
    "url": "https://example.com/paper2",
}

_PAPER_SAME_AUTHOR_YEAR = {
    "paper_id": "ghi789",
    "title": "Another Smith 2022 paper",
    "authors": "Smith, John",
    "year": "2022",
    "venue": "Science",
    "doi": "",
    "url": "",
}


class TestBibtexKey:
    def test_basic_key(self):
        assert bibtex_key(_PAPER_1) == "Smith2022"

    def test_no_year(self):
        paper = {**_PAPER_1, "year": ""}
        assert bibtex_key(paper) == "Smith"

    def test_no_authors(self):
        paper = {**_PAPER_1, "authors": ""}
        key = bibtex_key(paper)
        assert "2022" in key

    def test_collision_suffix(self):
        used: set[str] = set()
        k1 = bibtex_key(_PAPER_1, used)
        k2 = bibtex_key(_PAPER_SAME_AUTHOR_YEAR, used)
        assert k1 == "Smith2022"
        assert k2 == "Smith2022a"
        assert k1 != k2

    def test_no_collision_different_year(self):
        used: set[str] = set()
        k1 = bibtex_key(_PAPER_1, used)
        k2 = bibtex_key(_PAPER_2, used)
        assert k1 != k2


class TestGenerateBibtex:
    def test_empty(self):
        assert generate_bibtex([]) == ""

    def test_single_paper(self):
        bib = generate_bibtex([_PAPER_1])
        assert "@article{Smith2022," in bib
        assert "Deep Learning for Protein Folding" in bib
        assert "Smith, John" in bib
        assert "2022" in bib
        assert "Nature" in bib
        assert "10.1234/nature.2022" in bib

    def test_multiple_papers(self):
        bib = generate_bibtex([_PAPER_1, _PAPER_2])
        assert "@article{Smith2022," in bib
        assert "@article{Johnson2023," in bib

    def test_collision_handled(self):
        bib = generate_bibtex([_PAPER_1, _PAPER_SAME_AUTHOR_YEAR])
        assert "@article{Smith2022," in bib
        assert "@article{Smith2022a," in bib

    def test_missing_doi_omitted(self):
        bib = generate_bibtex([_PAPER_2])
        assert "doi" not in bib


class TestGenerateLatex:
    def _make_hyp(self, text, refs=None, score=0.8, generation=1, evolved_from=None):
        return {
            "id": "test01",
            "text": text,
            "score": score,
            "reflections": [],
            "generation": generation,
            "evolved_from": evolved_from,
            "references": refs or [],
        }

    def test_basic_structure(self):
        hyps = [self._make_hyp("Some hypothesis about protein folding.")]
        tex = generate_latex(hyps, [_PAPER_1], "protein folding", "Good findings.")
        assert r"\documentclass{article}" in tex
        assert r"\usepackage{natbib}" in tex
        assert r"\begin{document}" in tex
        assert r"\end{document}" in tex
        assert r"\bibliographystyle{plainnat}" in tex
        assert r"\bibliography{references}" in tex

    def test_hypothesis_section(self):
        hyps = [self._make_hyp("Proteins fold via energy minimization.")]
        tex = generate_latex(hyps, [_PAPER_1], "folding", "")
        assert r"\section{Hypothesis 1}" in tex
        assert "Proteins fold via energy minimization." in tex

    def test_citation_in_hypothesis(self):
        hyps = [self._make_hyp("Hypothesis with citation.", refs=["abc123"])]
        tex = generate_latex(hyps, [_PAPER_1], "topic", "")
        assert r"\citep{Smith2022}" in tex

    def test_no_citation_for_unknown_ref(self):
        hyps = [self._make_hyp("Hypothesis.", refs=["nonexistent_id"])]
        tex = generate_latex(hyps, [_PAPER_1], "topic", "")
        assert r"\citep{" not in tex

    def test_meta_review_section(self):
        hyps = [self._make_hyp("Hypothesis.")]
        tex = generate_latex(hyps, [], "topic", "Overall good quality.")
        assert r"\section{Meta-Review}" in tex
        assert "Overall good quality." in tex

    def test_no_meta_review_when_empty(self):
        hyps = [self._make_hyp("Hypothesis.")]
        tex = generate_latex(hyps, [], "topic", "")
        assert "Meta-Review" not in tex

    def test_score_and_lineage(self):
        hyps = [self._make_hyp("H", score=0.75, generation=2, evolved_from="parent01")]
        tex = generate_latex(hyps, [], "topic", "")
        assert "0.75" in tex
        assert "Generation 2" in tex
        assert "parent01" in tex

    def test_latex_escaping(self):
        hyps = [self._make_hyp("Costs $100 & more.")]
        tex = generate_latex(hyps, [], "topic with & ampersand", "")
        assert r"\$" in tex
        assert r"\&" in tex


class TestWriteOutput:
    def test_writes_files(self, tmp_path):
        hyps = [
            {
                "id": "h1",
                "text": "Hypothesis about AI.",
                "score": 0.9,
                "reflections": [],
                "generation": 1,
                "evolved_from": None,
                "references": ["abc123"],
            }
        ]
        write_output(tmp_path, hyps, [_PAPER_1], "AI research", "Meta notes.")
        assert (tmp_path / "hypotheses.tex").exists()
        assert (tmp_path / "references.bib").exists()

    def test_creates_output_dir(self, tmp_path):
        new_dir = tmp_path / "subdir" / "output"
        assert not new_dir.exists()
        write_output(new_dir, [], [], "topic", "")
        assert new_dir.exists()

    def test_file_contents(self, tmp_path):
        hyps = [
            {
                "id": "h1",
                "text": "Test hypothesis.",
                "score": 0.5,
                "reflections": [],
                "generation": 1,
                "evolved_from": None,
                "references": [],
            }
        ]
        write_output(tmp_path, hyps, [_PAPER_1], "test topic", "notes")
        tex = (tmp_path / "hypotheses.tex").read_text()
        bib = (tmp_path / "references.bib").read_text()
        assert "Test hypothesis." in tex
        assert "Smith2022" in bib


class TestGenerateTextOutput:
    def _make_hyp(self, text, refs=None, score=0.8, generation=1, evolved_from=None):
        return {
            "id": "test01",
            "text": text,
            "score": score,
            "reflections": [],
            "generation": generation,
            "evolved_from": evolved_from,
            "references": refs or [],
        }

    def test_basic_structure(self):
        hyps = [self._make_hyp("Some hypothesis about protein folding.")]
        text = generate_text_output(hyps, [_PAPER_1], "protein folding", "Good findings.", 5)
        assert "DARWIN CO-SCIENTIST RESEARCH RESULTS" in text
        assert "Topic: protein folding" in text
        assert "Max iterations: 5" in text
        assert "FINAL RANKED HYPOTHESES" in text
        assert "META-REVIEW SUMMARY" in text
        assert "LITERATURE SOURCES" in text

    def test_hypothesis_formatting(self):
        hyp = self._make_hyp("Proteins fold via energy minimization.", score=0.85, generation=2)
        text = generate_text_output([hyp], [], "folding", "", 3)
        assert "#1. [Score: 0.8500]" in text
        assert "Proteins fold via energy minimization." in text
        assert "Generation: 2" in text

    def test_hypothesis_with_evolution(self):
        hyp = self._make_hyp("Evolved hypothesis.", evolved_from="parent_hyp_123")
        text = generate_text_output([hyp], [], "topic", "")
        assert "Evolved from: parent_hyp_123" in text

    def test_hypothesis_with_references(self):
        hyp = self._make_hyp("Hypothesis with citation.", refs=["abc123"])
        text = generate_text_output([hyp], [_PAPER_1], "topic", "")
        assert "References:" in text
        assert "Smith, John" in text
        assert "(2022)" in text
        assert "Deep Learning for Protein Folding" in text
        assert "Nature" in text

    def test_multiple_hypotheses_ranked(self):
        hyps = [
            self._make_hyp("First hypothesis.", score=0.9),
            self._make_hyp("Second hypothesis.", score=0.7),
        ]
        text = generate_text_output(hyps, [], "topic", "")
        lines = text.split('\n')
        # Find the hypothesis ranking lines
        rank1_line = next(line for line in lines if "#1. [Score: 0.9000]" in line)
        rank2_line = next(line for line in lines if "#2. [Score: 0.7000]" in line)
        # Ensure rank 1 comes before rank 2
        assert lines.index(rank1_line) < lines.index(rank2_line)

    def test_meta_review_section(self):
        text = generate_text_output([], [], "topic", "This is the meta review.")
        assert "META-REVIEW SUMMARY" in text
        assert "This is the meta review." in text

    def test_no_meta_review_when_empty(self):
        text = generate_text_output([], [], "topic", "")
        # Should not have meta-review section when notes are empty
        assert "META-REVIEW SUMMARY" not in text

    def test_literature_sources_section(self):
        text = generate_text_output([], [_PAPER_1, _PAPER_2], "topic", "")
        assert "LITERATURE SOURCES" in text
        assert "Total papers referenced: 2" in text
        assert "Deep Learning for Protein Folding" in text
        assert "Transformer Architecture Advances" in text
        assert "DOI: 10.1234/nature.2022" in text

    def test_empty_hypotheses(self):
        text = generate_text_output([], [], "topic", "")
        assert "No hypotheses generated." in text

    def test_timestamp_and_footer(self):
        text = generate_text_output([], [], "topic", "")
        assert "Generated:" in text
        assert "Generated by Darwin Co-Scientist" in text


class TestWriteTextOutput:
    def test_writes_file(self, tmp_path):
        hyp = {
            "id": "h1",
            "text": "Test hypothesis for file output.",
            "score": 0.75,
            "reflections": [],
            "generation": 1,
            "evolved_from": None,
            "references": [],
        }
        output_file = tmp_path / "results.txt"
        write_text_output(output_file, [hyp], [], "test topic", "meta notes", 3)

        assert output_file.exists()
        content = output_file.read_text()
        assert "Test hypothesis for file output." in content
        assert "Max iterations: 3" in content

    def test_creates_output_dir(self, tmp_path):
        output_file = tmp_path / "subdir" / "results.txt"
        assert not output_file.parent.exists()
        write_text_output(output_file, [], [], "topic", "")
        assert output_file.parent.exists()
        assert output_file.exists()
