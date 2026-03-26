"""LLM prompt enhancement for inline citation generation."""
from __future__ import annotations

import json
from typing import Any


class CitationPromptEnhancer:
    """Enhances LLM prompts to encourage proper inline citation behavior."""

    def __init__(self):
        """Initialize the citation prompt enhancer."""
        self.citation_instructions = self._build_citation_instructions()

    def _build_citation_instructions(self) -> str:
        """Build comprehensive citation instructions for LLM prompts."""
        return """
CITATION REQUIREMENTS:
Every factual claim, research finding, or empirical assertion must include an inline citation.

Citation format: Use [paper_id] after claims that reference specific papers.
Example: "Recent studies show protein folding accuracy has improved significantly [smith2023protein]."

CLAIMS REQUIRING CITATIONS:
- Empirical findings: "Research shows...", "Studies indicate...", "Evidence suggests..."
- Statistical claims: Any numbers, percentages, correlations, or quantitative results
- Recent developments: "Recent advances...", "New methods...", "Latest techniques..."
- Established facts: References to known mechanisms, established pathways, or documented processes

CITATION PLACEMENT:
- Place citation immediately after the claim: "Machine learning improves accuracy [jones2022ml]."
- For multiple sources: "Deep learning shows promise [smith2023dl, brown2022ai, davis2023neural]."
- End-of-sentence placement is acceptable: "Protein prediction has advanced rapidly [multiple sources]."

DO NOT CITE:
- General background statements that don't make specific claims
- Your own reasoning or logical deductions
- Hypotheses you are generating (these should build on cited work)

AVAILABLE REFERENCES: {reference_list}
Use only paper_ids from the available references list. If no appropriate citation exists, rephrase to avoid making unsupported claims.
"""

    def enhance_generation_prompt(
        self,
        base_prompt: str,
        literature_context: list[dict[str, str]],
        enforce_citations: bool = True
    ) -> str:
        """Enhance a generation prompt to encourage proper citations.

        Args:
            base_prompt: Original prompt for hypothesis generation
            literature_context: Available literature for citations
            enforce_citations: Whether to strictly enforce citation requirements

        Returns:
            Enhanced prompt with citation instructions
        """
        # Build reference list for the prompt
        reference_list = []
        for paper in literature_context:
            paper_id = paper.get("paper_id", "")
            title = paper.get("title", "")
            authors = paper.get("authors", "")
            year = paper.get("year", "")

            if paper_id and title:
                ref_summary = f"[{paper_id}] {authors} ({year}): {title}"
                reference_list.append(ref_summary)

        reference_text = "\n".join(reference_list) if reference_list else "No references available"

        # Format citation instructions with actual references
        citation_section = self.citation_instructions.format(reference_list=reference_text)

        # Add enforcement section if enabled
        if enforce_citations:
            enforcement_text = """
STRICT REQUIREMENT: Every hypothesis MUST include at least one inline citation [paper_id]
unless it is purely theoretical reasoning. Hypotheses without proper citations will be rejected.

SELF-CHECK: Before outputting each hypothesis, verify:
1. Does this make any factual claims? → Add citations
2. Does this reference research findings? → Add citations
3. Is this based on established knowledge? → Add citations
4. Am I stating something as fact? → Add citations
"""
            citation_section += enforcement_text

        # Combine base prompt with citation requirements
        enhanced_prompt = f"""{base_prompt}

{citation_section}

Remember: Quality citations demonstrate that your hypotheses build on solid research foundations."""

        return enhanced_prompt

    def enhance_reflection_prompt(
        self,
        base_prompt: str,
        hypothesis_text: str,
        literature_context: list[dict[str, str]]
    ) -> str:
        """Enhance a reflection prompt to check citation quality.

        Args:
            base_prompt: Original reflection prompt
            hypothesis_text: Hypothesis text to reflect on
            literature_context: Available literature context

        Returns:
            Enhanced prompt that includes citation evaluation
        """
        citation_check_instructions = """
CITATION EVALUATION CRITERIA:
Assess the hypothesis for proper citation practices:

1. CLAIM IDENTIFICATION: Does the hypothesis make factual claims that need citations?
2. CITATION PRESENCE: Are appropriate inline citations [paper_id] included?
3. CITATION RELEVANCE: Do the cited papers actually support the claims made?
4. CITATION COMPLETENESS: Are all major claims properly supported?

Rate citation quality on a scale of 0.0-1.0:
- 1.0: All claims properly cited with relevant sources
- 0.7-0.9: Most claims cited, minor citation gaps
- 0.4-0.6: Some citations present but significant gaps
- 0.0-0.3: Few or no citations for claims that need them

Include citation assessment in your reflection and adjust the overall score accordingly.
Poor citation practices should significantly reduce the hypothesis score.
"""

        enhanced_prompt = f"""{base_prompt}

{citation_check_instructions}

HYPOTHESIS TO EVALUATE:
{hypothesis_text}

Include citation quality assessment in your reflection."""

        return enhanced_prompt

    def create_citation_repair_prompt(
        self,
        problematic_text: str,
        verification_results: list[Any],
        literature_context: list[dict[str, str]]
    ) -> str:
        """Create a prompt to repair citation issues in text.

        Args:
            problematic_text: Text with citation problems
            verification_results: Results from citation verification
            literature_context: Available literature for citations

        Returns:
            Prompt for fixing citation issues
        """
        # Analyze the verification results to provide specific guidance
        issues = []
        suggestions = []

        for result in verification_results:
            if not result.is_supported:
                sentence = result.requirement.sentence.text
                issue_desc = f"'{sentence}' - {result.reason}"
                issues.append(issue_desc)

                if result.available_but_unused:
                    for match in result.available_but_unused[:2]:  # Top 2 suggestions
                        suggestion = f"Consider citing [{match.paper_id}] for: {sentence}"
                        suggestions.append(suggestion)

        issues_text = "\n".join(f"- {issue}" for issue in issues)
        suggestions_text = "\n".join(f"- {suggestion}" for suggestion in suggestions)

        # Build reference list
        reference_list = []
        for paper in literature_context:
            paper_id = paper.get("paper_id", "")
            title = paper.get("title", "")
            if paper_id and title:
                reference_list.append(f"[{paper_id}]: {title}")

        references_text = "\n".join(reference_list)

        repair_prompt = f"""
TASK: Fix citation problems in the following text.

ORIGINAL TEXT:
{problematic_text}

IDENTIFIED CITATION ISSUES:
{issues_text}

SUGGESTED CITATIONS:
{suggestions_text}

AVAILABLE REFERENCES:
{references_text}

INSTRUCTIONS:
1. Keep the original meaning and content of the text
2. Add inline citations [paper_id] where needed
3. Ensure every factual claim has appropriate support
4. Use the format: "claim text [paper_id]" or "claim text [paper1, paper2]"
5. Only use paper_ids from the available references list

OUTPUT: The corrected text with proper inline citations.
"""

        return repair_prompt

    def add_citation_examples(self, prompt: str, domain: str = "general") -> str:
        """Add domain-specific citation examples to a prompt.

        Args:
            prompt: Base prompt to enhance
            domain: Research domain for targeted examples

        Returns:
            Prompt with relevant citation examples
        """
        examples = self._get_citation_examples(domain)

        examples_section = f"""
CITATION EXAMPLES FOR {domain.upper()}:
{examples}
"""

        return f"{prompt}\n\n{examples_section}"

    def _get_citation_examples(self, domain: str) -> str:
        """Get domain-specific citation examples."""
        examples = {
            "protein_folding": """
✓ GOOD: "AlphaFold2 achieved unprecedented accuracy in protein structure prediction [jumper2021alphafold]."
✓ GOOD: "Deep learning approaches have revolutionized structural biology [senior2020protein, evans2021fold]."
✗ BAD: "Machine learning is transforming protein folding." (no citation)
✗ BAD: "Recent studies show improvement." (vague, no specific citation)
""",
            "machine_learning": """
✓ GOOD: "Transformer architectures have shown remarkable performance in NLP tasks [vaswani2017attention]."
✓ GOOD: "Self-supervised learning reduces dependency on labeled data [chen2020simclr, he2020momentum]."
✗ BAD: "Deep learning works well for many problems." (no citation)
✗ BAD: "Neural networks are powerful." (too general, no citation)
""",
            "general": """
✓ GOOD: "Recent advances in computational methods have improved prediction accuracy [smith2023methods]."
✓ GOOD: "The proposed approach builds on established frameworks [jones2022framework, brown2023model]."
✗ BAD: "New methods are better than old ones." (no citation, vague)
✗ BAD: "Research shows this approach works." (no specific citation)
"""
        }

        return examples.get(domain, examples["general"])

    def create_hypothesis_validation_prompt(
        self,
        hypothesis: str,
        literature_context: list[dict[str, str]]
    ) -> str:
        """Create a prompt for validating hypothesis citations before finalization.

        Args:
            hypothesis: Hypothesis text to validate
            literature_context: Available literature context

        Returns:
            Validation prompt for checking citation quality
        """
        # Build available references summary
        references = []
        for paper in literature_context:
            paper_id = paper.get("paper_id", "")
            title = paper.get("title", "")
            authors = paper.get("authors", "")
            if paper_id:
                references.append(f"[{paper_id}]: {authors} - {title}")

        references_text = "\n".join(references)

        validation_prompt = f"""
TASK: Validate the citation quality of this hypothesis before final approval.

HYPOTHESIS:
{hypothesis}

AVAILABLE REFERENCES:
{references_text}

VALIDATION CHECKLIST:
1. CLAIM IDENTIFICATION: Identify all factual claims, research findings, or empirical assertions
2. CITATION PRESENCE: Check if each claim has appropriate inline citations [paper_id]
3. CITATION RELEVANCE: Verify cited papers actually support the claims made
4. CITATION COMPLETENESS: Ensure no major claims lack proper support

OUTPUT FORMAT:
{{
  "is_valid": true/false,
  "citation_score": 0.0-1.0,
  "issues_found": ["list of specific citation problems"],
  "suggestions": ["list of specific improvements"],
  "validated_hypothesis": "corrected version if changes needed"
}}

Be strict: hypotheses with poor citations should be marked invalid for revision.
"""

        return validation_prompt