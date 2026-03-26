"""Citation verification against literature context."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from darwin.citation_parser import CitationRequirement


@dataclass
class CitationMatch:
    """Represents a match between a claim and supporting reference."""
    paper_id: str
    paper_title: str
    match_score: float  # 0.0-1.0 how well the paper supports the claim
    match_reasons: list[str]  # explanations for why this paper matches
    relevant_content: list[str]  # specific quotes/sections that support the claim


@dataclass
class VerificationResult:
    """Result of verifying a citation requirement."""
    requirement: CitationRequirement
    is_supported: bool
    confidence: float  # 0.0-1.0 confidence in the verification result
    matches: list[CitationMatch]  # papers that support this claim
    available_but_unused: list[CitationMatch]  # papers that could support but aren't cited
    missing_citations: bool  # True if claim needs citations but has none
    reason: str  # human-readable explanation


class CitationVerifier:
    """Verifies claims against available literature context."""

    def __init__(self):
        """Initialize the citation verifier."""
        self.similarity_threshold = 0.4  # Minimum similarity for a match

    def _extract_paper_keywords(self, paper: dict[str, str]) -> set[str]:
        """Extract searchable keywords from a paper's metadata."""
        keywords = set()

        # Extract from title (most important)
        title = paper.get("title", "").lower()
        title_words = re.findall(r'\b[a-z]{3,}\b', title)
        keywords.update(title_words)

        # Extract from abstract if available
        abstract = paper.get("abstract", "").lower()
        if abstract:
            # Focus on nouns and important terms in abstract
            abstract_words = re.findall(r'\b[a-z]{4,}\b', abstract)
            # Take first 20 words to avoid noise
            keywords.update(abstract_words[:20])

        # Extract from authors (for citation matching)
        authors = paper.get("authors", "").lower()
        author_names = re.findall(r'\b[a-z]{2,}\b', authors)
        keywords.update(author_names)

        return keywords

    def _calculate_keyword_similarity(self, claim_keywords: list[str], paper_keywords: set[str]) -> float:
        """Calculate similarity between claim keywords and paper keywords."""
        if not claim_keywords or not paper_keywords:
            return 0.0

        claim_set = set(kw.lower() for kw in claim_keywords)
        matches = claim_set.intersection(paper_keywords)

        # Simple Jaccard similarity with weighting
        if not claim_set:
            return 0.0

        similarity = len(matches) / len(claim_set)

        # Boost similarity for longer matching terms
        for match in matches:
            if len(match) >= 6:  # Longer terms are more specific
                similarity += 0.1

        return min(similarity, 1.0)

    def _verify_existing_citations(
        self,
        requirement: CitationRequirement,
        literature_context: list[dict[str, str]]
    ) -> tuple[list[CitationMatch], list[str]]:
        """Verify that existing citations in the sentence actually support the claim."""
        verified_matches = []
        unverified_citations = []

        # Create lookup maps for paper references
        id_to_paper = {paper.get("paper_id", ""): paper for paper in literature_context}

        # Also create lookups by author-year patterns for natural citations
        author_year_to_paper = {}
        for paper in literature_context:
            authors = paper.get("authors", "")
            year = str(paper.get("year", ""))
            if authors and year:
                # Try different author-year formats
                first_author = authors.split(",")[0].split(" and ")[0].strip()
                if first_author:
                    key = f"{first_author} {year}"
                    author_year_to_paper[key.lower()] = paper

        for citation in requirement.existing_citations:
            paper = None

            # Try direct paper ID lookup
            if citation in id_to_paper:
                paper = id_to_paper[citation]
            else:
                # Try author-year lookup
                citation_lower = citation.lower()
                if citation_lower in author_year_to_paper:
                    paper = author_year_to_paper[citation_lower]
                else:
                    # Try partial matches for author-year citations
                    for key, candidate_paper in author_year_to_paper.items():
                        if (citation_lower in key or
                            any(word in key for word in citation_lower.split() if len(word) > 2)):
                            paper = candidate_paper
                            break

            if paper:
                # Verify this paper actually supports the claim
                match = self._assess_paper_relevance(requirement, paper)
                if match and match.match_score >= self.similarity_threshold:
                    verified_matches.append(match)
                else:
                    unverified_citations.append(citation)
            else:
                unverified_citations.append(citation)

        return verified_matches, unverified_citations

    def _assess_paper_relevance(self, requirement: CitationRequirement, paper: dict[str, str]) -> CitationMatch | None:
        """Assess how well a paper supports a specific claim."""
        paper_keywords = self._extract_paper_keywords(paper)
        keyword_similarity = self._calculate_keyword_similarity(requirement.keywords, paper_keywords)

        # Check for claim-type specific relevance
        claim_type_bonus = self._get_claim_type_bonus(requirement.claim_type, paper)

        # Combine scores
        match_score = (keyword_similarity * 0.7) + (claim_type_bonus * 0.3)

        if match_score < 0.1:  # Very low relevance
            return None

        # Determine match reasons
        reasons = []
        relevant_content = []

        if keyword_similarity > 0.3:
            matching_keywords = set(kw.lower() for kw in requirement.keywords).intersection(paper_keywords)
            reasons.append(f"Keyword overlap: {', '.join(sorted(matching_keywords))}")

        if claim_type_bonus > 0:
            reasons.append(f"Relevant to {requirement.claim_type} claims")

        # Extract relevant content (simplified - would be more sophisticated in practice)
        title = paper.get("title", "")
        if title:
            relevant_content.append(f"Title: {title}")

        abstract = paper.get("abstract", "")
        if abstract:
            # Extract first sentence as potentially relevant
            first_sentence = abstract.split('.')[0] if '.' in abstract else abstract[:200]
            relevant_content.append(f"Abstract: {first_sentence}...")

        return CitationMatch(
            paper_id=paper.get("paper_id", ""),
            paper_title=title,
            match_score=match_score,
            match_reasons=reasons,
            relevant_content=relevant_content
        )

    def _get_claim_type_bonus(self, claim_type: str, paper: dict[str, str]) -> float:
        """Get relevance bonus based on claim type and paper characteristics."""
        title = paper.get("title", "").lower()
        abstract = paper.get("abstract", "").lower()
        text_content = f"{title} {abstract}"

        bonus = 0.0

        if claim_type == "empirical_claim":
            # Look for research methodology indicators
            if any(term in text_content for term in ["study", "experiment", "analysis", "data", "results"]):
                bonus += 0.2

        elif claim_type == "statistical_claim":
            # Look for quantitative indicators
            if any(term in text_content for term in ["statistical", "significance", "p-value", "correlation", "regression"]):
                bonus += 0.3

        elif claim_type == "factual_assertion":
            # Look for established knowledge indicators
            if any(term in text_content for term in ["mechanism", "pathway", "established", "known"]):
                bonus += 0.2

        elif claim_type == "recent_advancement":
            # Boost score for newer papers
            year = paper.get("year", "")
            if year and year.isdigit():
                year_int = int(year)
                if year_int >= 2020:
                    bonus += 0.3
                elif year_int >= 2015:
                    bonus += 0.1

        return bonus

    def verify_citation_requirement(
        self,
        requirement: CitationRequirement,
        literature_context: list[dict[str, str]]
    ) -> VerificationResult:
        """Verify a citation requirement against available literature."""

        # First, verify existing citations
        verified_matches, unverified_citations = self._verify_existing_citations(requirement, literature_context)

        # Find additional papers that could support this claim
        potential_matches = []
        for paper in literature_context:
            # Skip papers already cited and verified
            paper_id = paper.get("paper_id", "")
            if any(match.paper_id == paper_id for match in verified_matches):
                continue

            match = self._assess_paper_relevance(requirement, paper)
            if match and match.match_score >= self.similarity_threshold:
                potential_matches.append(match)

        # Sort potential matches by score
        potential_matches.sort(key=lambda x: x.match_score, reverse=True)

        # Determine verification result
        all_supporting_papers = verified_matches + potential_matches
        has_citations = len(requirement.existing_citations) > 0
        has_valid_citations = len(verified_matches) > 0
        has_available_support = len(all_supporting_papers) > 0

        # Determine if the claim is properly supported
        is_supported = has_valid_citations
        confidence = 0.0
        reason = ""

        if is_supported:
            confidence = min(sum(match.match_score for match in verified_matches) / len(verified_matches), 1.0)
            reason = f"Claim supported by {len(verified_matches)} verified citation(s)"
        elif not has_citations and has_available_support:
            confidence = 0.3  # Low confidence - needs citations
            reason = f"Claim lacks citations but {len(potential_matches)} supporting papers available"
        elif has_citations and not has_valid_citations:
            confidence = 0.1  # Very low confidence - bad citations
            reason = f"Existing citations do not support the claim (unverified: {', '.join(unverified_citations)})"
        else:
            confidence = 0.0
            reason = "No supporting literature found for this claim"

        return VerificationResult(
            requirement=requirement,
            is_supported=is_supported,
            confidence=confidence,
            matches=verified_matches,
            available_but_unused=potential_matches[:5],  # Top 5 unused matches
            missing_citations=not has_citations and has_available_support,
            reason=reason
        )

    def verify_text(
        self,
        text: str,
        literature_context: list[dict[str, str]],
        parser: Any = None
    ) -> list[VerificationResult]:
        """Verify all citation requirements in a text."""
        if parser is None:
            from darwin.citation_parser import CitationParser
            parser = CitationParser()

        requirements = parser.parse_for_citations(text)
        results = []

        for requirement in requirements:
            result = self.verify_citation_requirement(requirement, literature_context)
            results.append(result)

        return results