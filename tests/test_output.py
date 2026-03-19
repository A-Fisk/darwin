"""Tests for output.py — BibTeX and LaTeX generation."""
from __future__ import annotations

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
    def test_basic_key_with_topic(self):
        # New behavior includes topic keywords from title
        key = bibtex_key(_PAPER_1)
        assert key == "smithDoe2022DeepLearning"  # Smith+Doe (2 authors) + year + topic

    def test_single_author_key(self):
        # Test single author case
        key = bibtex_key(_PAPER_SAME_AUTHOR_YEAR)
        assert key == "smith2022AnotherSmith"

    def test_no_year(self):
        paper = {**_PAPER_1, "year": ""}
        key = bibtex_key(paper)
        assert key == "smithDoeDeepLearning"  # No year, but has authors and topic

    def test_no_authors(self):
        paper = {**_PAPER_1, "authors": ""}
        key = bibtex_key(paper)
        assert key == "unknown2022DeepLearning"  # Default author + year + topic

    def test_no_title(self):
        paper = {**_PAPER_1, "title": ""}
        key = bibtex_key(paper)
        assert key == "smithDoe2022"  # Authors + year, no topic

    def test_collision_suffix(self):
        used: set[str] = set()
        k1 = bibtex_key(_PAPER_1, used)
        # Create a paper that would generate the same key
        paper_collision = {
            "paper_id": "collision",
            "title": "Deep Learning for Something Else",  # Same topic keywords
            "authors": "Smith, John, Doe, Jane",  # Same authors
            "year": "2022",  # Same year
        }
        k2 = bibtex_key(paper_collision, used)
        assert k1 == "smithDoe2022DeepLearning"
        assert k2 == "smithDoe2022DeepLearninga"  # Collision suffix
        assert k1 != k2

    def test_no_collision_different_year(self):
        used: set[str] = set()
        k1 = bibtex_key(_PAPER_1, used)
        k2 = bibtex_key(_PAPER_2, used)
        assert k1 != k2  # Different authors, years, and topics

    def test_three_authors_et_al(self):
        paper_three = {
            "paper_id": "three",
            "title": "Multi Author Machine Learning Study",
            "authors": "Smith, John and Doe, Jane and Wilson, Bob",
            "year": "2023",
        }
        key = bibtex_key(paper_three)
        assert key == "smithEtAl2023MultiAuthor"

    def test_keyword_extraction(self):
        paper_keywords = {
            "paper_id": "keywords",
            "title": "Neural Networks for Sleep Spindle Detection in EEG",
            "authors": "Smith, John",
            "year": "2023",
        }
        key = bibtex_key(paper_keywords)
        assert key == "smith2023NeuralNetworks"  # Should pick meaningful keywords

    def test_stop_words_filtered(self):
        paper_stopwords = {
            "paper_id": "stop",
            "title": "A Study on the Analysis of Machine Learning",  # Many stop words
            "authors": "Smith, John",
            "year": "2023",
        }
        key = bibtex_key(paper_stopwords)
        assert key == "smith2023MachineLearning"  # Should skip stop words

    def test_long_key_truncation(self):
        paper_long = {
            "paper_id": "long",
            "title": "Very Long Title With Many Keywords That Should Be Truncated Appropriately",
            "authors": "VeryLongSurnameIndeed, John",
            "year": "2023",
        }
        key = bibtex_key(paper_long)
        assert len(key) <= 50  # Should be truncated
        assert "verylongsurnameindeed2023" in key  # Should contain author+year


class TestGenerateBibtex:
    def test_empty(self):
        assert generate_bibtex([]) == ""

    def test_single_paper(self):
        bib = generate_bibtex([_PAPER_1])
        # Key should now be better-bibtex style
        assert "@article{smithDoe2022DeepLearning," in bib
        assert "Deep Learning for Protein Folding" in bib
        assert "Smith, John" in bib
        assert "2022" in bib
        assert "Nature" in bib
        assert "10.1234/nature.2022" in bib

    def test_multiple_papers(self):
        bib = generate_bibtex([_PAPER_1, _PAPER_2])
        assert "@article{smithDoe2022DeepLearning," in bib
        assert "@article{johnsonLee2023TransformerArchitecture," in bib

    def test_collision_handled(self):
        bib = generate_bibtex([_PAPER_1, _PAPER_SAME_AUTHOR_YEAR])
        assert "@article{smithDoe2022DeepLearning," in bib
        assert "@article{smith2022AnotherSmith," in bib

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
        assert r"\citep{smithDoe2022DeepLearning}" in tex

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

    def test_in_text_citations_with_claims(self):
        hyps = [self._make_hyp("Recent studies show that protein folding follows energy minimization.", refs=["abc123"])]
        tex = generate_latex(hyps, [_PAPER_1], "topic", "")
        # Should have in-text citation within the hypothesis text
        assert "Recent studies show that protein folding follows energy minimization \\citep{Smith2022}." in tex
        # Should also still have the references section
        assert r"\textbf{References:} \citep{Smith2022}" in tex

    def test_in_text_citations_keyword_matching(self):
        hyps = [self._make_hyp("Machine learning advances and transformer models improve accuracy.", refs=["abc123", "def456"])]
        # Create papers with distinct keywords
        papers = [
            _PAPER_1,  # Deep Learning for Protein Folding
            {**_PAPER_2, "title": "Transformer Neural Networks"}  # Changed title for clearer keyword matching
        ]
        tex = generate_latex(hyps, papers, "topic", "")
        # Should match "transformer" keyword to the second paper (Johnson2023)
        assert "transformer models improve accuracy \\citep{Johnson2023}." in tex

    def test_in_text_citations_no_claims(self):
        hyps = [self._make_hyp("This is a simple statement without claims.", refs=["abc123"])]
        tex = generate_latex(hyps, [_PAPER_1], "topic", "")
        # Should not have in-text citations for non-claim sentences
        assert "\\citep{" not in tex.split("\\textbf{References:}")[0]  # Before the References section
        # But should still have the references section
        assert r"\textbf{References:} \citep{Smith2022}" in tex

    def test_in_text_citations_multiple_sentences(self):
        hyps = [self._make_hyp("Recent research shows improvements. Furthermore, deep learning advances accuracy.", refs=["abc123"])]
        tex = generate_latex(hyps, [_PAPER_1], "topic", "")
        # Both sentences should get citations since they have claim indicators
        hypothesis_section = tex.split("\\textbf{Score:}")[0]  # Get hypothesis text only
        citation_count = hypothesis_section.count("\\citep{Smith2022}")
        assert citation_count == 2

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
        assert "smithDoe2022DeepLearning" in bib


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
