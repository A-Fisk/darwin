"""Citation verification pipeline for real-time integration with Darwin workflow."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from darwin.citation_logger import CitationLogger
from darwin.citation_parser import CitationParser
from darwin.citation_verifier import CitationVerifier, VerificationResult
from darwin.state import Hypothesis, ResearchState


class CitationPipeline:
    """Main pipeline for citation verification integration."""

    def __init__(self, log_dir: str | Path | None = None, enable_logging: bool = True):
        """Initialize the citation verification pipeline.

        Args:
            log_dir: Directory for citation logs (defaults to 'logs/citations')
            enable_logging: Whether to enable failure logging
        """
        self.parser = CitationParser()
        self.verifier = CitationVerifier()

        self.enable_logging = enable_logging
        if self.enable_logging:
            if log_dir is None:
                # Default to logs directory in project root
                log_dir = Path.cwd() / "logs" / "citations"
            self.logger = CitationLogger(log_dir)
        else:
            self.logger = None

    def verify_hypothesis(
        self,
        hypothesis: Hypothesis,
        literature_context: list[dict[str, str]],
        agent_name: str | None = None,
        iteration: int | None = None
    ) -> list[VerificationResult]:
        """Verify citations in a single hypothesis.

        Args:
            hypothesis: The hypothesis to verify
            literature_context: Available literature for verification
            agent_name: Name of the agent that generated this hypothesis
            iteration: Current research iteration

        Returns:
            List of verification results for each claim in the hypothesis
        """
        hypothesis_text = hypothesis.get("text", "")
        hypothesis_id = hypothesis.get("id", "")

        # Parse and verify the hypothesis text
        results = self.verifier.verify_text(hypothesis_text, literature_context, self.parser)

        # Log results if logging is enabled
        if self.logger:
            for result in results:
                if result.is_supported:
                    self.logger.log_citation_success(
                        result,
                        agent_name=agent_name,
                        task_description="hypothesis_verification",
                        hypothesis_id=hypothesis_id,
                        iteration=iteration
                    )
                else:
                    self.logger.log_citation_failure(
                        result,
                        agent_name=agent_name,
                        task_description="hypothesis_verification",
                        hypothesis_id=hypothesis_id,
                        iteration=iteration
                    )

        return results

    def verify_research_state(
        self,
        state: ResearchState,
        agent_name: str | None = None
    ) -> dict[str, list[VerificationResult]]:
        """Verify citations for all hypotheses in current research state.

        Args:
            state: Current research state containing hypotheses and literature
            agent_name: Name of the agent performing verification

        Returns:
            Dict mapping hypothesis IDs to their verification results
        """
        hypotheses = state.get("hypotheses", [])
        literature_context = state.get("literature_context", [])
        iteration = state.get("iteration", 0)

        verification_results = {}

        for hypothesis in hypotheses:
            hypothesis_id = hypothesis.get("id", "")
            results = self.verify_hypothesis(
                hypothesis,
                literature_context,
                agent_name=agent_name,
                iteration=iteration
            )
            verification_results[hypothesis_id] = results

        return verification_results

    def get_citation_report(self, results: list[VerificationResult]) -> dict[str, Any]:
        """Generate a summary report of citation verification results.

        Args:
            results: List of verification results to summarize

        Returns:
            Summary report with statistics and recommendations
        """
        if not results:
            return {
                "total_claims": 0,
                "supported_claims": 0,
                "unsupported_claims": 0,
                "missing_citations": 0,
                "overall_score": 1.0,
                "recommendations": []
            }

        total_claims = len(results)
        supported_claims = sum(1 for r in results if r.is_supported)
        unsupported_claims = total_claims - supported_claims
        missing_citations = sum(1 for r in results if r.missing_citations)

        # Calculate overall citation score
        if total_claims > 0:
            confidence_sum = sum(r.confidence for r in results)
            overall_score = confidence_sum / total_claims
        else:
            overall_score = 1.0

        # Generate recommendations
        recommendations = []

        if missing_citations > 0:
            recommendations.append(
                f"Add citations to {missing_citations} claim(s) that lack proper references"
            )

        # Find claims with available but unused citations
        available_unused = [r for r in results if not r.is_supported and r.available_but_unused]
        if available_unused:
            recommendations.append(
                f"Utilize available references for {len(available_unused)} unsupported claim(s)"
            )

        # Find claims with invalid existing citations
        invalid_citations = [r for r in results if r.requirement.existing_citations and not r.matches]
        if invalid_citations:
            recommendations.append(
                f"Review {len(invalid_citations)} claim(s) with potentially invalid citations"
            )

        return {
            "total_claims": total_claims,
            "supported_claims": supported_claims,
            "unsupported_claims": unsupported_claims,
            "missing_citations": missing_citations,
            "overall_score": overall_score,
            "recommendations": recommendations,
            "detailed_results": [
                {
                    "sentence": r.requirement.sentence.text,
                    "claim_type": r.requirement.claim_type,
                    "is_supported": r.is_supported,
                    "confidence": r.confidence,
                    "reason": r.reason,
                    "existing_citations": r.requirement.existing_citations,
                    "available_matches": len(r.available_but_unused)
                }
                for r in results
            ]
        }

    def suggest_citations(
        self,
        text: str,
        literature_context: list[dict[str, str]],
        max_suggestions: int = 3
    ) -> dict[str, Any]:
        """Suggest citations for claims in text that need them.

        Args:
            text: Text to analyze for citation opportunities
            literature_context: Available literature for citations
            max_suggestions: Maximum number of citation suggestions per claim

        Returns:
            Dictionary with citation suggestions for each claim
        """
        results = self.verifier.verify_text(text, literature_context, self.parser)

        suggestions = {
            "suggestions": [],
            "summary": {
                "claims_analyzed": len(results),
                "claims_needing_citations": 0,
                "total_suggestions": 0
            }
        }

        for result in results:
            if not result.is_supported and result.available_but_unused:
                suggestions["summary"]["claims_needing_citations"] += 1

                claim_suggestions = {
                    "sentence": result.requirement.sentence.text,
                    "claim_type": result.requirement.claim_type,
                    "position": {
                        "start": result.requirement.sentence.start_pos,
                        "end": result.requirement.sentence.end_pos
                    },
                    "suggested_citations": []
                }

                # Take top matches up to max_suggestions
                for match in result.available_but_unused[:max_suggestions]:
                    claim_suggestions["suggested_citations"].append({
                        "paper_id": match.paper_id,
                        "paper_title": match.paper_title,
                        "relevance_score": match.match_score,
                        "reasons": match.match_reasons
                    })

                suggestions["suggestions"].append(claim_suggestions)
                suggestions["summary"]["total_suggestions"] += len(claim_suggestions["suggested_citations"])

        return suggestions

    def enable_automatic_citation_enforcement(self) -> bool:
        """Check if automatic citation enforcement should be enabled.

        This could be controlled by environment variables or configuration files.

        Returns:
            True if automatic enforcement should be enabled
        """
        # Check for environment variable
        env_setting = os.getenv("DARWIN_ENFORCE_CITATIONS", "false").lower()
        return env_setting in ("true", "1", "yes", "on")

    def get_failure_statistics(self, days: int = 30) -> dict[str, Any] | None:
        """Get citation failure statistics from logs.

        Args:
            days: Number of days back to analyze

        Returns:
            Statistics dictionary or None if logging disabled
        """
        if not self.logger:
            return None

        return self.logger.get_failure_statistics(days)


# Singleton instance for easy access throughout the Darwin system
_default_pipeline: CitationPipeline | None = None


def get_citation_pipeline() -> CitationPipeline:
    """Get the default citation pipeline instance."""
    global _default_pipeline
    if _default_pipeline is None:
        _default_pipeline = CitationPipeline()
    return _default_pipeline


def verify_hypothesis_citations(
    hypothesis: Hypothesis,
    literature_context: list[dict[str, str]],
    agent_name: str | None = None,
    iteration: int | None = None
) -> list[VerificationResult]:
    """Convenience function to verify a single hypothesis using the default pipeline."""
    pipeline = get_citation_pipeline()
    return pipeline.verify_hypothesis(hypothesis, literature_context, agent_name, iteration)