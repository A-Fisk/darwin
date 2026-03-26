"""Configuration and CLI interface for citation verification system."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from darwin.citation_pipeline import CitationPipeline


def create_citation_cli() -> argparse.ArgumentParser:
    """Create CLI parser for citation verification commands."""
    parser = argparse.ArgumentParser(
        description="Darwin Citation Verification System",
        prog="darwin-citations"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify citations in text")
    verify_parser.add_argument("--text", required=True, help="Text to verify")
    verify_parser.add_argument("--literature", required=True, help="JSON file with literature context")
    verify_parser.add_argument("--output", help="Output file for results (JSON)")

    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show citation failure statistics")
    stats_parser.add_argument("--days", type=int, default=30, help="Days back to analyze")
    stats_parser.add_argument("--log-dir", help="Citation logs directory")

    # Config command
    config_parser = subparsers.add_parser("config", help="Manage citation configuration")
    config_parser.add_argument("--enable", action="store_true", help="Enable citation verification")
    config_parser.add_argument("--disable", action="store_true", help="Disable citation verification")
    config_parser.add_argument("--show", action="store_true", help="Show current configuration")

    # Test command
    test_parser = subparsers.add_parser("test", help="Run citation system tests")
    test_parser.add_argument("--smoke-test", action="store_true", help="Run basic smoke tests")

    return parser


def verify_citations_cli(text: str, literature_file: str, output_file: str | None = None) -> None:
    """CLI command to verify citations in text."""
    # Load literature context
    try:
        with open(literature_file) as f:
            literature_context = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading literature file: {e}", file=sys.stderr)
        sys.exit(1)

    # Verify citations
    pipeline = CitationPipeline(enable_logging=False)
    results = pipeline.verifier.verify_text(text, literature_context)

    # Generate report
    report = pipeline.get_citation_report(results)

    if output_file:
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)
        print(f"Results written to {output_file}")
    else:
        print(json.dumps(report, indent=2))


def show_citation_stats(days: int = 30, log_dir: str | None = None) -> None:
    """CLI command to show citation failure statistics."""
    pipeline = CitationPipeline(log_dir=log_dir, enable_logging=True)
    stats = pipeline.get_failure_statistics(days)

    if not stats:
        print("No statistics available (logging may be disabled)")
        return

    print(f"Citation Failure Statistics (Last {days} days)")
    print("=" * 50)
    print(f"Total failures: {stats['total_failures']}")
    print(f"Average available references: {stats['avg_available_references']:.1f}")
    print()

    if stats["failures_by_type"]:
        print("Failures by claim type:")
        for claim_type, count in sorted(stats["failures_by_type"].items()):
            print(f"  {claim_type}: {count}")
        print()

    if stats["failures_by_agent"]:
        print("Failures by agent:")
        for agent, count in sorted(stats["failures_by_agent"].items()):
            print(f"  {agent}: {count}")
        print()

    if stats["common_failure_reasons"]:
        print("Common failure reasons:")
        for reason, count in sorted(stats["common_failure_reasons"].items(), key=lambda x: x[1], reverse=True):
            print(f"  {reason}: {count}")


def manage_citation_config(enable: bool = False, disable: bool = False, show: bool = False) -> None:
    """CLI command to manage citation verification configuration."""
    if show:
        enforce = os.getenv("DARWIN_ENFORCE_CITATIONS", "false")
        assess = os.getenv("DARWIN_ASSESS_CITATIONS", "true")
        logging = os.getenv("DARWIN_CITATION_LOGGING", "true")

        print("Current Citation Configuration:")
        print(f"  Enforce citations: {enforce}")
        print(f"  Assess citation quality: {assess}")
        print(f"  Enable logging: {logging}")
        return

    if enable:
        os.environ["DARWIN_ENFORCE_CITATIONS"] = "true"
        os.environ["DARWIN_ASSESS_CITATIONS"] = "true"
        print("Citation verification enabled")

    if disable:
        os.environ["DARWIN_ENFORCE_CITATIONS"] = "false"
        os.environ["DARWIN_ASSESS_CITATIONS"] = "false"
        print("Citation verification disabled")


def run_citation_tests(smoke_test: bool = False) -> None:
    """CLI command to run citation system tests."""
    if smoke_test:
        print("Running citation system smoke tests...")

        # Import and run the smoke tests from the test file
        try:
            # This would run the smoke tests defined in test_citation_system.py
            from tests.test_citation_system import (
                CitationParser,
                CitationVerifier,
                CitationPipeline
            )
            import tempfile

            # Basic functionality test
            parser = CitationParser()
            requirements = parser.parse_for_citations("Studies show that AI improves accuracy.")
            print(f"✓ Parser identified {len(requirements)} citation requirements")

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

        except ImportError as e:
            print(f"Could not run tests: {e}")
            print("Make sure the citation system modules are properly installed.")
        except Exception as e:
            print(f"Test failed: {e}")
            sys.exit(1)
    else:
        print("Use --smoke-test for basic functionality tests")
        print("For full test suite, run: python -m pytest tests/test_citation_system.py")


def main() -> None:
    """Main CLI entry point."""
    parser = create_citation_cli()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "verify":
            verify_citations_cli(args.text, args.literature, args.output)

        elif args.command == "stats":
            show_citation_stats(args.days, args.log_dir)

        elif args.command == "config":
            manage_citation_config(args.enable, args.disable, args.show)

        elif args.command == "test":
            run_citation_tests(args.smoke_test)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()