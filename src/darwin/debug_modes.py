"""Debug modes for fast development with minimal LLM calls.

This module provides different debug modes that can significantly reduce or eliminate
LLM calls for faster development iteration and testing.
"""
from __future__ import annotations

import random
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from darwin.state import Hypothesis


@dataclass
class DebugConfig:
    """Configuration for debug modes."""

    # Core debug mode settings
    mode: Literal["off", "fast", "minimal", "mock"] = "off"

    # Specific agent overrides (True = use mock, False = use real LLM)
    mock_literature: bool = False
    mock_generation: bool = False
    mock_reflection: bool = False
    mock_supervisor: bool = False
    mock_ranking: bool = False
    mock_evolution: bool = False
    mock_meta_review: bool = False

    # Mock data settings
    use_sample_papers: bool = True
    use_template_hypotheses: bool = True
    add_artificial_delay: bool = False  # Simulate LLM latency for UI testing

    @classmethod
    def from_mode(cls, mode: Literal["off", "fast", "minimal", "mock"]) -> DebugConfig:
        """Create debug config from predefined mode."""
        if mode == "off":
            return cls(mode="off")
        elif mode == "fast":
            # Reduce LLM calls but keep core functionality
            return cls(
                mode="fast",
                mock_literature=True,  # Use sample papers
                mock_ranking=True,     # Skip expensive pairwise comparisons
                mock_evolution=True,   # Simple mutations without LLM
                use_sample_papers=True,
                use_template_hypotheses=False,
            )
        elif mode == "minimal":
            # Only use LLMs for generation and reflection (core research loop)
            return cls(
                mode="minimal",
                mock_literature=True,
                mock_supervisor=True,
                mock_ranking=True,
                mock_evolution=True,
                mock_meta_review=True,
                use_sample_papers=True,
                use_template_hypotheses=False,
            )
        elif mode == "mock":
            # Mock everything for pure UI/flow testing
            return cls(
                mode="mock",
                mock_literature=True,
                mock_generation=True,
                mock_reflection=True,
                mock_supervisor=True,
                mock_ranking=True,
                mock_evolution=True,
                mock_meta_review=True,
                use_sample_papers=True,
                use_template_hypotheses=True,
                add_artificial_delay=True,
            )
        else:
            raise ValueError(f"Unknown debug mode: {mode}")


# Global debug configuration
_debug_config = DebugConfig()


def set_debug_mode(mode: Literal["off", "fast", "minimal", "mock"]) -> None:
    """Set the global debug mode."""
    global _debug_config
    _debug_config = DebugConfig.from_mode(mode)


def reset_debug_mode() -> None:
    """Reset debug mode to default (off). Used for test isolation."""
    global _debug_config
    _debug_config = DebugConfig()


def get_debug_config() -> DebugConfig:
    """Get the current debug configuration."""
    return _debug_config


def should_mock_agent(agent_name: str) -> bool:
    """Check if a specific agent should use mock behavior."""
    config = get_debug_config()
    mock_map = {
        "literature": config.mock_literature,
        "generation": config.mock_generation,
        "reflection": config.mock_reflection,
        "supervisor": config.mock_supervisor,
        "ranking": config.mock_ranking,
        "evolution": config.mock_evolution,
        "meta_review": config.mock_meta_review,
    }
    return mock_map.get(agent_name, False)


def artificial_delay() -> None:
    """Add artificial delay to simulate LLM latency if configured."""
    if _debug_config.add_artificial_delay:
        time.sleep(random.uniform(0.5, 2.0))


# Sample data for mock modes
SAMPLE_PAPERS = [
    {
        "paper_id": "sample_001",
        "title": "Mechanisms of Antibiotic Resistance in Hospital Pathogens",
        "abstract": (
            "A comprehensive review of how bacterial pathogens develop and spread "
            "antibiotic resistance in healthcare settings through horizontal gene transfer, "
            "biofilm formation, and selective pressure from antibiotic use."
        ),
        "authors": "Smith, J., Johnson, A., Brown, K.",
        "year": "2023",
        "venue": "Nature Medicine",
        "doi": "10.1038/s41591-023-sample",
        "url": "https://example.com/sample_001",
    },
    {
        "paper_id": "sample_002",
        "title": "Biofilm Formation and Medical Device Infections",
        "abstract": (
            "Investigation of how bacterial biofilms form on medical devices and create protected "
            "environments for resistance gene acquisition and transmission."
        ),
        "authors": "Davis, L., Wilson, M., Garcia, R.",
        "year": "2023",
        "venue": "Clinical Microbiology Reviews",
        "doi": "10.1128/cmr-sample-002",
        "url": "https://example.com/sample_002",
    },
    {
        "paper_id": "sample_003",
        "title": "Horizontal Gene Transfer in ICU Environments",
        "abstract": (
            "Analysis of conjugative plasmid transfer rates in intensive care unit bacterial "
            "populations and their role in multi-drug resistance spread."
        ),
        "authors": "Lee, C., Martinez, P., Thompson, S.",
        "year": "2022",
        "venue": "The Lancet Infectious Diseases",
        "doi": "10.1016/s1473-sample-003",
        "url": "https://example.com/sample_003",
    }
]

HYPOTHESIS_TEMPLATES = [
    (
        "Horizontal gene transfer via conjugative plasmids is the primary mechanism "
        "of {topic_key} in hospital settings"
    ),
    (
        "Biofilm formation on medical devices creates protected niches that enable "
        "{topic_key} through reduced antibiotic penetration"
    ),
    (
        "Sub-therapeutic antibiotic concentrations in ICU environments select for "
        "{topic_key} variants with intermediate resistance"
    ),
    (
        "Quorum sensing systems coordinate {topic_key} responses across bacterial "
        "populations during hospital outbreaks"
    ),
    (
        "Efflux pump upregulation provides a rapid adaptive response to {topic_key} "
        "selective pressure in clinical isolates"
    ),
]


def generate_mock_hypotheses(topic: str, count: int = 5, iteration: int = 1) -> list[Hypothesis]:
    """Generate mock hypotheses using templates."""
    if not _debug_config.use_template_hypotheses:
        raise ValueError("Template hypotheses disabled in current debug mode")

    # Extract key terms from topic for template substitution
    topic_lower = topic.lower()
    if "antibiotic" in topic_lower and "resistance" in topic_lower:
        topic_key = "antibiotic resistance spread"
    elif "carbon" in topic_lower and "capture" in topic_lower:
        topic_key = "carbon sequestration"
    elif "neural" in topic_lower or "brain" in topic_lower:
        topic_key = "neural pathway activation"
    else:
        topic_key = "the observed phenomenon"

    hypotheses = []
    for i in range(min(count, len(HYPOTHESIS_TEMPLATES))):
        template = HYPOTHESIS_TEMPLATES[i]
        text = template.format(topic_key=topic_key)

        # Add some variation to avoid identical hypotheses
        if i > 0:
            variations = [
                f"{text} through enhanced bacterial communication",
                f"{text} via novel enzymatic pathways",
                f"{text} mediated by environmental stress responses"
            ]
            text = random.choice(variations)

        hypotheses.append(
            Hypothesis(
                id=uuid.uuid4().hex[:8],
                text=text,
                score=random.uniform(0.3, 0.8),  # Realistic score range
                reflections=[f"Mock reflection for hypothesis {i+1}"],
                generation=iteration,
                evolved_from=None,
                references=random.sample(
                    [p["paper_id"] for p in SAMPLE_PAPERS], k=random.randint(0, 2)
                )
            )
        )

    return hypotheses


def get_mock_literature_context() -> list[dict[str, str]]:
    """Get mock literature data."""
    if not _debug_config.use_sample_papers:
        return []
    return SAMPLE_PAPERS.copy()


def mock_supervisor_decision(iteration: int, max_iterations: int, top_hypotheses: list[Any]) -> str:
    """Generate mock supervisor decision."""
    if iteration >= max_iterations:
        return "stop"
    elif iteration > 2 and random.random() < 0.1:  # 10% chance of human review
        return "human_review"
    else:
        return "continue"


def mock_reflection_score() -> tuple[str, float]:
    """Generate mock reflection critique and score."""
    critiques = [
        "This hypothesis demonstrates good scientific rigor and testability.",
        "Strong mechanistic basis but could benefit from more specific predictions.",
        "Novel approach with clear experimental pathways for validation.",
        "Well-grounded in literature but needs more precise quantitative predictions.",
        "Interesting connection between established mechanisms, testable with current methods."
    ]
    return random.choice(critiques), random.uniform(0.4, 0.9)


def mock_ranking_scores(hypotheses: list[Hypothesis]) -> list[Hypothesis]:
    """Generate mock ranking scores for hypotheses."""
    # Simple ranking based on existing scores with some noise
    ranked = sorted(hypotheses, key=lambda h: h["score"] + random.uniform(-0.1, 0.1), reverse=True)

    # Normalize scores to 0-1 range (simple ranking-based normalization)
    if ranked:
        for i, h in enumerate(ranked):
            # Give top hypotheses better scores
            normalized = 1.0 - (i / len(ranked)) * 0.7  # Top gets 1.0, bottom gets 0.3
            h["score"] = normalized

    return ranked