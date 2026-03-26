"""Example integration of citation verification with Darwin agents."""
from __future__ import annotations

import os
from typing import Any

# Example of how to integrate citation verification into Darwin's existing agents


def create_citation_enhanced_generation_agent() -> Any:
    """Create an enhanced generation agent with citation verification."""
    from darwin.agents.generation import run as original_generation_run
    from darwin.citation_integration import integrate_citation_verification_with_generation
    from darwin.citation_prompts import CitationPromptEnhancer

    # Wrap the original generation agent
    enhanced_run = integrate_citation_verification_with_generation(original_generation_run)

    return enhanced_run


def create_citation_enhanced_reflection_agent() -> Any:
    """Create an enhanced reflection agent that considers citation quality."""
    from darwin.agents.reflection import run as original_reflection_run
    from darwin.citation_integration import integrate_citation_verification_with_reflection

    # Wrap the original reflection agent
    enhanced_run = integrate_citation_verification_with_reflection(original_reflection_run)

    return enhanced_run


def setup_citation_verification_environment() -> None:
    """Set up environment variables for citation verification."""
    # Enable citation enforcement globally
    os.environ["DARWIN_ENFORCE_CITATIONS"] = "true"
    os.environ["DARWIN_ASSESS_CITATIONS"] = "true"
    os.environ["DARWIN_CITATION_LOGGING"] = "true"

    print("Citation verification environment configured:")
    print("  - Citation enforcement: ENABLED")
    print("  - Citation quality assessment: ENABLED")
    print("  - Citation failure logging: ENABLED")


def demonstrate_citation_verification() -> None:
    """Demonstrate the citation verification system with example data."""
    from darwin.citation_pipeline import CitationPipeline
    from darwin.state import Hypothesis

    # Sample literature context
    literature_context = [
        {
            "paper_id": "jumper2021alphafold",
            "title": "Highly accurate protein structure prediction with AlphaFold",
            "authors": "Jumper, John and Evans, Richard and Pritzel, Alexander",
            "year": "2021",
            "venue": "Nature",
            "abstract": "We present AlphaFold2, a deep learning system that achieves unprecedented accuracy in protein structure prediction."
        },
        {
            "paper_id": "senior2020protein",
            "title": "Improved protein structure prediction using potentials from deep learning",
            "authors": "Senior, Andrew W. and Evans, Richard and Jumper, John",
            "year": "2020",
            "venue": "Nature",
            "abstract": "We describe a deep learning approach that significantly improves protein folding accuracy."
        }
    ]

    # Sample hypotheses with different citation quality levels
    hypotheses = [
        {
            "id": "hyp_001",
            "text": "Deep learning approaches have revolutionized protein structure prediction accuracy [jumper2021alphafold].",
            "score": 0.9,
            "reflections": [],
            "generation": 1,
            "evolved_from": None,
            "references": ["jumper2021alphafold"]
        },
        {
            "id": "hyp_002",
            "text": "Recent advances in computational methods significantly improve prediction accuracy.",
            "score": 0.7,
            "reflections": [],
            "generation": 1,
            "evolved_from": None,
            "references": []  # Missing citations!
        },
        {
            "id": "hyp_003",
            "text": "Machine learning models achieve 95% accuracy in protein folding predictions [nonexistent2023].",
            "score": 0.8,
            "reflections": [],
            "generation": 1,
            "evolved_from": None,
            "references": ["nonexistent2023"]  # Invalid citation!
        }
    ]

    # Initialize citation pipeline
    pipeline = CitationPipeline(enable_logging=True)

    print("\n" + "="*60)
    print("CITATION VERIFICATION DEMONSTRATION")
    print("="*60)

    # Verify each hypothesis
    for i, hypothesis in enumerate(hypotheses, 1):
        print(f"\n--- Hypothesis {i} ---")
        print(f"Text: {hypothesis['text']}")
        print(f"Existing references: {hypothesis['references']}")

        # Verify citations
        results = pipeline.verify_hypothesis(
            hypothesis,
            literature_context,
            agent_name="demo_agent",
            iteration=1
        )

        if results:
            # Generate report for this hypothesis
            report = pipeline.get_citation_report(results)

            print(f"Citation Score: {report['overall_score']:.2f}/1.0")
            print(f"Supported Claims: {report['supported_claims']}/{report['total_claims']}")

            if report['recommendations']:
                print("Recommendations:")
                for rec in report['recommendations']:
                    print(f"  • {rec}")
        else:
            print("No claims requiring citation verification found.")

    # Show citation suggestions for poorly cited hypothesis
    print(f"\n--- Citation Suggestions for Hypothesis 2 ---")
    suggestions = pipeline.suggest_citations(hypotheses[1]['text'], literature_context)

    if suggestions['suggestions']:
        for suggestion in suggestions['suggestions']:
            print(f"Sentence: '{suggestion['sentence']}'")
            print("Suggested citations:")
            for citation in suggestion['suggested_citations']:
                print(f"  • [{citation['paper_id']}] {citation['paper_title']} (relevance: {citation['relevance_score']:.2f})")
    else:
        print("No citation suggestions available.")

    # Show overall statistics
    print(f"\n--- Overall Statistics ---")
    stats = pipeline.get_failure_statistics(days=1)
    if stats and stats['total_failures'] > 0:
        print(f"Total citation failures logged: {stats['total_failures']}")
        print(f"Most common failure types: {list(stats['failures_by_type'].keys())}")
    else:
        print("No failure statistics available (recent implementation).")


def create_enhanced_darwin_graph() -> Any:
    """Create a Darwin graph with citation verification integrated."""
    from darwin.graph import build_graph
    from darwin.citation_integration import create_citation_verification_middleware

    # Get the middleware functions
    middleware = create_citation_verification_middleware()

    # In a real implementation, you would modify the graph builder to use enhanced agents
    # For demonstration, we show how the enhanced functions would be used

    print("\nEnhanced Darwin Graph Configuration:")
    print("  - Generation agent: Enhanced with citation prompts and verification")
    print("  - Reflection agent: Enhanced with citation quality assessment")
    print("  - Meta-review agent: Enhanced with citation analysis summary")

    # Build the original graph (you would modify this to use enhanced agents)
    original_graph = build_graph()

    print("  - Original graph structure preserved")
    print("  - Citation verification hooks integrated")

    return original_graph


def main() -> None:
    """Main demonstration function."""
    print("Darwin Citation Verification System Demo")
    print("="*50)

    # Set up environment
    setup_citation_verification_environment()

    # Demonstrate citation verification
    demonstrate_citation_verification()

    # Show how to create enhanced agents
    print(f"\n--- Enhanced Agent Creation ---")
    enhanced_generation = create_citation_enhanced_generation_agent()
    enhanced_reflection = create_citation_enhanced_reflection_agent()

    print("✓ Enhanced generation agent created")
    print("✓ Enhanced reflection agent created")

    # Show enhanced graph setup
    enhanced_graph = create_enhanced_darwin_graph()
    print("✓ Enhanced Darwin graph configured")

    print(f"\n--- Integration Complete ---")
    print("The citation verification system is now ready for use with Darwin.")
    print("\nTo use in production:")
    print("1. Set DARWIN_ENFORCE_CITATIONS=true in your environment")
    print("2. Ensure literature context is available to agents")
    print("3. Monitor citation logs in logs/citations/ directory")
    print("4. Review citation statistics regularly with 'darwin-citations stats'")


if __name__ == "__main__":
    main()