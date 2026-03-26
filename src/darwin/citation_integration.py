"""Integration hooks for citation verification in Darwin workflow."""
from __future__ import annotations

import os
from typing import Any

from darwin.citation_pipeline import CitationPipeline, get_citation_pipeline
from darwin.citation_prompts import CitationPromptEnhancer
from darwin.state import Hypothesis, ResearchState


def integrate_citation_verification_with_generation(original_generation_func: Any) -> Any:
    """Decorator to integrate citation verification with hypothesis generation.

    This wraps the generation agent to enhance prompts with citation instructions
    and optionally verify generated hypotheses.
    """
    def enhanced_generation(state: ResearchState) -> dict[str, object]:
        """Enhanced generation that includes citation requirements."""
        # Check if citation enforcement is enabled
        enforce_citations = os.getenv("DARWIN_ENFORCE_CITATIONS", "false").lower() in ("true", "1", "yes")

        # Get literature context for citation enhancement
        literature_context = state.get("literature_context", [])

        # If we have citation enhancement enabled, we could modify the generation
        # process here. For now, just run the original and verify results.
        result = original_generation_func(state)

        # Verify citations in generated hypotheses if enforcement is enabled
        if enforce_citations and literature_context:
            pipeline = get_citation_pipeline()
            new_hypotheses = result.get("hypotheses", [])

            for hypothesis in new_hypotheses:
                verification_results = pipeline.verify_hypothesis(
                    hypothesis,
                    literature_context,
                    agent_name="generation",
                    iteration=state.get("iteration", 0)
                )

                # Store verification results in hypothesis metadata
                hypothesis["citation_verification"] = {
                    "verified": any(r.is_supported for r in verification_results),
                    "total_claims": len(verification_results),
                    "supported_claims": sum(1 for r in verification_results if r.is_supported),
                    "verification_score": sum(r.confidence for r in verification_results) / len(verification_results) if verification_results else 1.0
                }

        return result

    return enhanced_generation


def integrate_citation_verification_with_reflection(original_reflection_func: Any) -> Any:
    """Decorator to integrate citation quality assessment with reflection.

    This enhances the reflection agent to consider citation quality when scoring hypotheses.
    """
    def enhanced_reflection(state: ResearchState) -> dict[str, object]:
        """Enhanced reflection that includes citation quality assessment."""
        # Run original reflection
        result = original_reflection_func(state)

        # Check if citation assessment should be included
        assess_citations = os.getenv("DARWIN_ASSESS_CITATIONS", "true").lower() in ("true", "1", "yes")

        if assess_citations:
            literature_context = state.get("literature_context", [])
            pipeline = get_citation_pipeline()

            # Update hypothesis scores based on citation quality
            hypotheses = result.get("hypotheses", [])
            for hypothesis in hypotheses:
                if literature_context:
                    verification_results = pipeline.verify_hypothesis(
                        hypothesis,
                        literature_context,
                        agent_name="reflection",
                        iteration=state.get("iteration", 0)
                    )

                    if verification_results:
                        citation_score = sum(r.confidence for r in verification_results) / len(verification_results)

                        # Adjust overall hypothesis score based on citation quality
                        original_score = hypothesis.get("score", 0.0)
                        citation_weight = 0.2  # 20% weight for citations

                        adjusted_score = (original_score * (1 - citation_weight)) + (citation_score * citation_weight)
                        hypothesis["score"] = adjusted_score

                        # Add citation quality to reflections
                        reflections = hypothesis.get("reflections", [])
                        citation_reflection = f"Citation quality score: {citation_score:.2f}"

                        if citation_score < 0.5:
                            citation_reflection += " - Insufficient citation support for claims"
                        elif citation_score < 0.8:
                            citation_reflection += " - Some claims lack proper citations"
                        else:
                            citation_reflection += " - Well-supported with appropriate citations"

                        reflections.append(citation_reflection)
                        hypothesis["reflections"] = reflections

        return result

    return enhanced_reflection


def add_citation_verification_to_meta_review(original_meta_review_func: Any) -> Any:
    """Decorator to add citation analysis to meta-review stage."""
    def enhanced_meta_review(state: ResearchState) -> dict[str, object]:
        """Enhanced meta-review that includes citation quality analysis."""
        result = original_meta_review_func(state)

        # Add citation quality summary to meta-review notes
        literature_context = state.get("literature_context", [])
        if literature_context:
            pipeline = get_citation_pipeline()

            # Analyze citation quality across all hypotheses
            all_hypotheses = state.get("final_hypotheses", []) or state.get("top_hypotheses", [])
            citation_stats = {
                "total_hypotheses": len(all_hypotheses),
                "well_cited_hypotheses": 0,
                "poorly_cited_hypotheses": 0,
                "total_citation_score": 0.0
            }

            for hypothesis in all_hypotheses:
                verification_results = pipeline.verify_hypothesis(
                    hypothesis,
                    literature_context,
                    agent_name="meta_review",
                    iteration=state.get("iteration", 0)
                )

                if verification_results:
                    citation_score = sum(r.confidence for r in verification_results) / len(verification_results)
                    citation_stats["total_citation_score"] += citation_score

                    if citation_score >= 0.7:
                        citation_stats["well_cited_hypotheses"] += 1
                    else:
                        citation_stats["poorly_cited_hypotheses"] += 1

            # Calculate average citation quality
            if citation_stats["total_hypotheses"] > 0:
                avg_citation_score = citation_stats["total_citation_score"] / citation_stats["total_hypotheses"]

                # Add citation analysis to meta-review notes
                existing_notes = result.get("meta_review_notes", "")
                citation_analysis = f"""

CITATION QUALITY ANALYSIS:
- Average citation score: {avg_citation_score:.2f}/1.0
- Well-cited hypotheses: {citation_stats['well_cited_hypotheses']}/{citation_stats['total_hypotheses']}
- Hypotheses needing citation improvement: {citation_stats['poorly_cited_hypotheses']}

Citation recommendations:
"""

                if avg_citation_score < 0.5:
                    citation_analysis += "- CRITICAL: Many hypotheses lack proper citation support\n"
                    citation_analysis += "- Review literature context and add relevant citations\n"
                elif avg_citation_score < 0.8:
                    citation_analysis += "- MODERATE: Some hypotheses need better citation support\n"
                    citation_analysis += "- Consider adding more specific references to claims\n"
                else:
                    citation_analysis += "- GOOD: Hypotheses are generally well-supported with citations\n"

                result["meta_review_notes"] = existing_notes + citation_analysis

        return result

    return enhanced_meta_review


def create_citation_verification_middleware() -> dict[str, Any]:
    """Create middleware functions for integrating citation verification across Darwin.

    Returns:
        Dictionary of middleware functions that can be applied to Darwin agents
    """
    return {
        "generation_enhancer": integrate_citation_verification_with_generation,
        "reflection_enhancer": integrate_citation_verification_with_reflection,
        "meta_review_enhancer": add_citation_verification_to_meta_review,
    }


def enable_citation_verification_globally() -> None:
    """Enable citation verification for the Darwin system by setting environment variables."""
    os.environ["DARWIN_ENFORCE_CITATIONS"] = "true"
    os.environ["DARWIN_ASSESS_CITATIONS"] = "true"


def disable_citation_verification_globally() -> None:
    """Disable citation verification for the Darwin system."""
    os.environ["DARWIN_ENFORCE_CITATIONS"] = "false"
    os.environ["DARWIN_ASSESS_CITATIONS"] = "false"


def get_citation_verification_config() -> dict[str, bool]:
    """Get current citation verification configuration.

    Returns:
        Dictionary with current configuration settings
    """
    return {
        "enforce_citations": os.getenv("DARWIN_ENFORCE_CITATIONS", "false").lower() in ("true", "1", "yes"),
        "assess_citations": os.getenv("DARWIN_ASSESS_CITATIONS", "true").lower() in ("true", "1", "yes"),
        "logging_enabled": os.getenv("DARWIN_CITATION_LOGGING", "true").lower() in ("true", "1", "yes")
    }


def create_citation_enhanced_prompts(
    literature_context: list[dict[str, str]],
    domain: str = "general"
) -> CitationPromptEnhancer:
    """Create a citation prompt enhancer configured for the current context.

    Args:
        literature_context: Available literature for the current research session
        domain: Research domain for targeted examples

    Returns:
        Configured CitationPromptEnhancer instance
    """
    enhancer = CitationPromptEnhancer()

    # Pre-configure with current literature context
    enhancer.current_literature = literature_context
    enhancer.current_domain = domain

    return enhancer