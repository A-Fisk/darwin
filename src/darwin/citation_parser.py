"""Citation parsing and sentence analysis for verification."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import NamedTuple


class Sentence(NamedTuple):
    """Represents a parsed sentence with metadata."""
    text: str
    start_pos: int
    end_pos: int


@dataclass
class CitationRequirement:
    """Represents a sentence that requires citation verification."""
    sentence: Sentence
    claim_type: str  # e.g., "empirical_claim", "statistical_claim", "factual_assertion"
    confidence: float  # 0.0-1.0 how confident we are this needs citation
    existing_citations: list[str]  # citations already present in the sentence
    keywords: list[str]  # key terms that could match reference content


class CitationParser:
    """Parser to identify sentences requiring citations and extract existing ones."""

    # Patterns that indicate claims requiring citations
    CLAIM_PATTERNS = {
        "empirical_claim": [
            r'\b(studies?|research|findings?|evidence|demonstrates?|shows?|indicates?|suggests?|reports?)\b',
            r'\b(according to|based on|as shown|research shows?|evidence suggests?)\b',
            r'\b(results? indicate|data shows?|analysis reveals?)\b',
        ],
        "statistical_claim": [
            r'\b(\d+%|\d+\s*percent|significant|correlation|p\s*[<>=]\s*\d|statistical)\b',
            r'\b(increased by|decreased by|higher than|lower than|more likely)\b',
            r'\b(odds ratio|confidence interval|standard deviation|mean|median)\b',
        ],
        "factual_assertion": [
            r'\b(protein folding|machine learning|deep learning|neural networks?|algorithms?)\b',
            r'\b(established|known|proven|documented|recognized)\b',
            r'\b(mechanism|pathway|process|technique|method)\b',
        ],
        "recent_advancement": [
            r'\b(recent|new|novel|latest|breakthrough|advancement|development)\b',
            r'\b(state-of-the-art|cutting-?edge|innovative|emerging)\b',
        ]
    }

    # Patterns for existing citations in text
    CITATION_PATTERNS = [
        r'\(([^)]+\s+\d{4}[a-z]?)\)',  # (Author 2023) or (Author et al. 2023a)
        r'\[(\d+(?:,\s*\d+)*)\]',      # [1] or [1,2,3]
        r'\\citep?\{([^}]+)\}',         # LaTeX citations
    ]

    def __init__(self):
        """Initialize the citation parser."""
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self.compiled_claim_patterns = {}
        for claim_type, patterns in self.CLAIM_PATTERNS.items():
            self.compiled_claim_patterns[claim_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]

        self.compiled_citation_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.CITATION_PATTERNS
        ]

    def parse_text(self, text: str) -> list[Sentence]:
        """Parse text into individual sentences with position tracking."""
        # Split on sentence boundaries but preserve positions
        sentences = []

        # Use a more sophisticated sentence splitter
        sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

        start = 0
        for match in sentence_pattern.finditer(text):
            sentence_text = text[start:match.start()].strip()
            if sentence_text:
                sentences.append(Sentence(
                    text=sentence_text,
                    start_pos=start,
                    end_pos=match.start()
                ))
            start = match.end()

        # Add the last sentence
        if start < len(text):
            sentence_text = text[start:].strip()
            if sentence_text:
                sentences.append(Sentence(
                    text=sentence_text,
                    start_pos=start,
                    end_pos=len(text)
                ))

        return sentences

    def extract_existing_citations(self, sentence_text: str) -> list[str]:
        """Extract any existing citations from a sentence."""
        citations = []

        for pattern in self.compiled_citation_patterns:
            matches = pattern.findall(sentence_text)
            citations.extend(matches)

        # Clean and normalize citation keys
        clean_citations = []
        for citation in citations:
            # Handle comma-separated citation lists
            if ',' in citation:
                clean_citations.extend([c.strip() for c in citation.split(',')])
            else:
                clean_citations.append(citation.strip())

        return clean_citations

    def identify_claim_type(self, sentence_text: str) -> tuple[str | None, float]:
        """Identify if sentence contains claims requiring citation."""
        best_claim_type = None
        best_confidence = 0.0

        for claim_type, patterns in self.compiled_claim_patterns.items():
            confidence = 0.0
            matches = 0

            for pattern in patterns:
                if pattern.search(sentence_text):
                    matches += 1
                    confidence += 0.3  # Each pattern match increases confidence

            # Normalize confidence based on number of patterns
            if matches > 0:
                confidence = min(confidence, 1.0)  # Cap at 1.0

                # Boost confidence for multiple matches
                if matches > 1:
                    confidence = min(confidence * 1.2, 1.0)

                if confidence > best_confidence:
                    best_confidence = confidence
                    best_claim_type = claim_type

        return best_claim_type, best_confidence

    def extract_keywords(self, sentence_text: str) -> list[str]:
        """Extract key terms that could match against reference content."""
        # Remove common words and extract meaningful terms
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off',
            'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
            'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few',
            'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
            'own', 'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just',
            'should', 'now'
        }

        # Clean text and extract words
        clean_text = re.sub(r'[^\w\s-]', '', sentence_text.lower())
        words = [w.strip() for w in clean_text.split() if len(w.strip()) >= 3]

        # Filter meaningful keywords
        keywords = []
        for word in words:
            if (word not in stopwords and
                len(word) >= 3 and
                re.search(r'[a-z]', word) and
                not word.isdigit()):
                keywords.append(word)

        return keywords

    def analyze_sentence(self, sentence: Sentence) -> CitationRequirement | None:
        """Analyze a sentence to determine if it requires citation verification."""
        claim_type, confidence = self.identify_claim_type(sentence.text)

        # Only process sentences with sufficient claim confidence
        if claim_type is None or confidence < 0.3:
            return None

        existing_citations = self.extract_existing_citations(sentence.text)
        keywords = self.extract_keywords(sentence.text)

        return CitationRequirement(
            sentence=sentence,
            claim_type=claim_type,
            confidence=confidence,
            existing_citations=existing_citations,
            keywords=keywords
        )

    def parse_for_citations(self, text: str) -> list[CitationRequirement]:
        """Parse text and return all sentences requiring citation verification."""
        sentences = self.parse_text(text)
        requirements = []

        for sentence in sentences:
            requirement = self.analyze_sentence(sentence)
            if requirement:
                requirements.append(requirement)

        return requirements