"""Tests for citation verification system."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from darwin.citation_logger import CitationLogger
from darwin.citation_parser import CitationParser, CitationRequirement
from darwin.citation_pipeline import CitationPipeline
from darwin.citation_verifier import CitationVerifier
from darwin.state import Hypothesis


class TestCitationParser:
    """Test cases for citation parsing functionality."""

    def test_sentence_parsing(self):
        """Test basic sentence parsing with position tracking."""
        parser = CitationParser()
        text = "First sentence. Second sentence! Third sentence?"

        sentences = parser.parse_text(text)

        assert len(sentences) == 3
        assert sentences[0].text == "First sentence."
        assert sentences[1].text == "Second sentence!"
        assert sentences[2].text == "Third sentence?"

    def test_claim_identification(self):
        """Test identification of claims requiring citations."""
        parser = CitationParser()

        # Test empirical claims
        empirical_text = "Studies show that protein folding accuracy has improved."
        claim_type, confidence = parser.identify_claim_type(empirical_text)
        assert claim_type == "empirical_claim"
        assert confidence >= 0.3

        # Test statistical claims
        statistical_text = "The model achieved 95% accuracy with p < 0.01."
        claim_type, confidence = parser.identify_claim_type(statistical_text)
        assert claim_type == "statistical_claim"
        assert confidence >= 0.3

        # Test non-claims - use simple descriptive text
        non_claim_text = "Here is some simple text without claims."
        claim_type, confidence = parser.identify_claim_type(non_claim_text)
        # Most text should either have no claim type or very low confidence
        if claim_type is not None:
            assert confidence <= 0.3

    def test_existing_citation_extraction(self):
        """Test extraction of existing citations from text."""
        parser = CitationParser()

        # Test various citation formats
        text_with_citations = "Research shows improvement (Smith 2023) and others \\citep{jones2022}."
        citations = parser.extract_existing_citations(text_with_citations)

        assert "Smith 2023" in citations
        assert "jones2022" in citations

    def test_keyword_extraction(self):
        """Test keyword extraction from sentences."""
        parser = CitationParser()

        text = "Machine learning algorithms improve protein folding prediction accuracy."
        keywords = parser.extract_keywords(text)

        assert "machine" in keywords
        assert "learning" in keywords
        assert "algorithms" in keywords
        assert "protein" in keywords
        assert "folding" in keywords
        # Stop words should be excluded
        assert "the" not in keywords
        assert "and" not in keywords

    def test_full_citation_analysis(self):
        """Test complete citation requirement analysis."""
        parser = CitationParser()

        text = "Recent studies demonstrate that deep learning significantly improves protein structure prediction."
        requirements = parser.parse_for_citations(text)

        assert len(requirements) == 1
        requirement = requirements[0]
        assert isinstance(requirement, CitationRequirement)
        assert requirement.claim_type in ["empirical_claim", "recent_advancement"]
        assert requirement.confidence >= 0.3
        assert "deep" in requirement.keywords
        assert "learning" in requirement.keywords


class TestCitationVerifier:
    """Test cases for citation verification functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.verifier = CitationVerifier()
        self.sample_literature = [
            {
                "paper_id": "smith2023protein",
                "title": "Deep Learning Approaches for Protein Structure Prediction",
                "authors": "Smith, John and Doe, Jane",
                "year": "2023",
                "abstract": "This paper presents novel deep learning methods for protein folding prediction with improved accuracy.",
                "venue": "Nature Methods"
            },
            {
                "paper_id": "jones2022ml",
                "title": "Machine Learning in Computational Biology",
                "authors": "Jones, Alice",
                "year": "2022",
                "abstract": "Comprehensive review of machine learning applications in biological research.",
                "venue": "Cell"
            }
        ]

    def test_keyword_similarity_calculation(self):
        """Test keyword similarity calculation between claims and papers."""
        paper_keywords = {"deep", "learning", "protein", "structure", "prediction"}
        claim_keywords = ["deep", "learning", "accuracy"]

        similarity = self.verifier._calculate_keyword_similarity(claim_keywords, paper_keywords)
        assert 0.5 < similarity < 1.0  # Should have decent overlap

    def test_paper_relevance_assessment(self):
        """Test assessment of paper relevance to claims."""
        parser = CitationParser()
        requirement = parser.analyze_sentence(
            parser.parse_text("Deep learning improves protein folding accuracy.")[0]
        )

        match = self.verifier._assess_paper_relevance(requirement, self.sample_literature[0])

        assert match is not None
        assert match.match_score > 0.4
        assert "protein" in str(match.match_reasons).lower()

    def test_citation_verification_with_valid_citations(self):
        """Test verification when valid citations are present."""
        parser = CitationParser()
        text = "Deep learning improves protein prediction accuracy [smith2023protein]."

        requirements = parser.parse_for_citations(text)
        assert len(requirements) == 1

        result = self.verifier.verify_citation_requirement(requirements[0], self.sample_literature)

        assert result.is_supported
        assert result.confidence > 0.5
        assert len(result.matches) > 0

    def test_citation_verification_missing_citations(self):
        """Test verification when citations are missing but literature is available."""
        parser = CitationParser()
        text = "Studies show that deep learning significantly improves protein folding accuracy."

        requirements = parser.parse_for_citations(text)
        result = self.verifier.verify_citation_requirement(requirements[0], self.sample_literature)

        assert not result.is_supported
        assert result.missing_citations
        assert len(result.available_but_unused) > 0


class TestCitationLogger:
    """Test cases for citation logging functionality."""

    def test_failure_logging(self):
        """Test logging of citation failures."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = CitationLogger(temp_dir)

            # Create a mock verification result
            parser = CitationParser()
            verifier = CitationVerifier()

            text = "Studies show improvement without citations."
            requirements = parser.parse_for_citations(text)
            result = verifier.verify_citation_requirement(requirements[0], [])

            # Log the failure
            logger.log_citation_failure(
                result,
                agent_name="test_agent",
                task_description="test_task",
                hypothesis_id="test_hyp_123"
            )

            # Verify log file was created and contains entry
            failure_log = Path(temp_dir) / "citation_failures.jsonl"
            assert failure_log.exists()

            with open(failure_log) as f:
                entries = [json.loads(line) for line in f]

            assert len(entries) == 1
            entry = entries[0]
            assert entry["sentence_text"] == "Studies show improvement without citations."
            assert entry["context"]["agent_name"] == "test_agent"
            assert entry["context"]["hypothesis_id"] == "test_hyp_123"

    def test_success_logging(self):
        """Test logging of successful citation verifications."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = CitationLogger(temp_dir)

            # Create a mock successful verification with better supporting literature
            parser = CitationParser()
            verifier = CitationVerifier()

            literature = [{
                "paper_id": "test123",
                "title": "Research Demonstrates Machine Learning Effectiveness",
                "authors": "Test Author",
                "year": "2023",
                "abstract": "This research demonstrates the effectiveness of machine learning algorithms in various applications."
            }]

            text = "Research demonstrates machine learning effectiveness [test123]."
            requirements = parser.parse_for_citations(text)
            result = verifier.verify_citation_requirement(requirements[0], literature)

            logger.log_citation_success(
                result,
                agent_name="test_agent",
                hypothesis_id="test_hyp_456"
            )

            success_log = Path(temp_dir) / "citation_successes.jsonl"
            assert success_log.exists()

    def test_statistics_generation(self):
        """Test failure statistics generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = CitationLogger(temp_dir)

            # Create multiple log entries using text that will generate citation requirements
            parser = CitationParser()
            verifier = CitationVerifier()

            for i in range(3):
                text = f"Studies show that test claim {i} demonstrates significant improvement."
                requirements = parser.parse_for_citations(text)
                # Ensure we have requirements before proceeding
                assert len(requirements) > 0, f"No requirements generated for text: {text}"

                result = verifier.verify_citation_requirement(requirements[0], [])

                logger.log_citation_failure(
                    result,
                    agent_name=f"agent_{i % 2}",  # Alternate agents
                    hypothesis_id=f"hyp_{i}"
                )

            stats = logger.get_failure_statistics(days=1)

            assert stats["total_failures"] == 3
            assert "agent_0" in stats["failures_by_agent"]
            assert "agent_1" in stats["failures_by_agent"]


class TestCitationPipeline:
    """Test cases for the integrated citation pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.literature = [
            {
                "paper_id": "example2023",
                "title": "Example Research Paper",
                "authors": "Example, Author",
                "year": "2023",
                "abstract": "This paper studies machine learning applications."
            }
        ]

        self.sample_hypothesis: Hypothesis = {
            "id": "test_hyp_123",
            "text": "Machine learning algorithms show significant improvement in accuracy.",
            "score": 0.8,
            "reflections": [],
            "generation": 1,
            "evolved_from": None,
            "references": ["example2023"]
        }

    def test_hypothesis_verification(self):
        """Test verification of a complete hypothesis."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = CitationPipeline(log_dir=temp_dir, enable_logging=True)

            results = pipeline.verify_hypothesis(
                self.sample_hypothesis,
                self.literature,
                agent_name="test_agent",
                iteration=1
            )

            assert len(results) >= 1
            # Should have some verification results for the hypothesis

    def test_citation_report_generation(self):
        """Test generation of citation quality reports."""
        pipeline = CitationPipeline(enable_logging=False)

        results = pipeline.verifier.verify_text(
            "Studies show improvement. Research indicates progress.",
            self.literature
        )

        report = pipeline.get_citation_report(results)

        assert "total_claims" in report
        assert "supported_claims" in report
        assert "overall_score" in report
        assert "recommendations" in report

    def test_citation_suggestions(self):
        """Test generation of citation suggestions."""
        pipeline = CitationPipeline(enable_logging=False)

        text = "Machine learning has shown remarkable progress in recent years."
        suggestions = pipeline.suggest_citations(text, self.literature)

        assert "suggestions" in suggestions
        assert "summary" in suggestions


if __name__ == "__main__":
    # Run basic smoke tests if executed directly
    print("Running citation system smoke tests...")

    # Test parser
    parser = CitationParser()
    requirements = parser.parse_for_citations("Studies show that AI improves accuracy.")
    print(f"✓ Parser identified {len(requirements)} citation requirements")

    # Test verifier
    verifier = CitationVerifier()
    sample_lit = [{
        "paper_id": "test123",
        "title": "AI Research Paper",
        "authors": "Test Author",
        "year": "2023"
    }]

    if requirements:
        result = verifier.verify_citation_requirement(requirements[0], sample_lit)
        print(f"✓ Verifier result: supported={result.is_supported}, confidence={result.confidence:.2f}")

    # Test pipeline
    with tempfile.TemporaryDirectory() as temp_dir:
        pipeline = CitationPipeline(log_dir=temp_dir)
        hypothesis = {
            "id": "test",
            "text": "AI research demonstrates significant improvements.",
            "score": 0.8,
            "reflections": [],
            "generation": 1,
            "evolved_from": None,
            "references": []
        }

        results = pipeline.verify_hypothesis(hypothesis, sample_lit)
        print(f"✓ Pipeline processed hypothesis with {len(results)} verification results")

    print("All smoke tests passed! ✓")