"""Append-only logging system for citation verification failures."""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from darwin.citation_verifier import VerificationResult


class CitationLogger:
    """Thread-safe append-only logger for citation verification events."""

    def __init__(self, log_dir: str | Path = "logs/citations"):
        """Initialize the citation logger.

        Args:
            log_dir: Directory to store citation log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create separate log files for different event types
        self.failure_log = self.log_dir / "citation_failures.jsonl"
        self.success_log = self.log_dir / "citation_successes.jsonl"
        self.retry_log = self.log_dir / "citation_retries.jsonl"

        # Thread lock for safe concurrent logging
        self._lock = threading.Lock()

    def _write_log_entry(self, log_file: Path, entry: dict[str, Any]) -> None:
        """Thread-safely append a log entry to the specified file."""
        with self._lock:
            # Append mode ensures we don't overwrite existing entries
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _create_base_entry(
        self,
        result: VerificationResult,
        context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create base log entry with common fields."""
        timestamp = datetime.utcnow().isoformat() + "Z"
        req = result.requirement

        entry = {
            "timestamp": timestamp,
            "sentence_text": req.sentence.text,
            "sentence_position": {
                "start": req.sentence.start_pos,
                "end": req.sentence.end_pos
            },
            "claim_type": req.claim_type,
            "claim_confidence": req.confidence,
            "existing_citations": req.existing_citations,
            "keywords": req.keywords,
            "verification_result": {
                "is_supported": result.is_supported,
                "confidence": result.confidence,
                "reason": result.reason,
                "missing_citations": result.missing_citations,
                "verified_matches_count": len(result.matches),
                "available_unused_count": len(result.available_but_unused)
            }
        }

        # Add context information if provided
        if context:
            entry["context"] = context

        return entry

    def log_citation_failure(
        self,
        result: VerificationResult,
        agent_name: str | None = None,
        task_description: str | None = None,
        hypothesis_id: str | None = None,
        iteration: int | None = None
    ) -> None:
        """Log a citation verification failure.

        Args:
            result: The verification result containing the failure
            agent_name: Name of the agent that generated the text
            task_description: Description of the task being performed
            hypothesis_id: ID of the hypothesis being processed
            iteration: Research iteration number
        """
        if result.is_supported:
            return  # Not a failure

        context = {
            "agent_name": agent_name,
            "task_description": task_description,
            "hypothesis_id": hypothesis_id,
            "iteration": iteration,
            "failure_type": "citation_verification_failed"
        }

        entry = self._create_base_entry(result, context)

        # Add failure-specific information
        entry["failure_details"] = {
            "available_references": [
                {
                    "paper_id": match.paper_id,
                    "paper_title": match.paper_title,
                    "match_score": match.match_score,
                    "match_reasons": match.match_reasons
                }
                for match in result.available_but_unused
            ],
            "unverified_existing_citations": [],  # Could extract from verifier if needed
            "suggested_action": self._suggest_fix_action(result)
        }

        self._write_log_entry(self.failure_log, entry)

    def log_citation_success(
        self,
        result: VerificationResult,
        agent_name: str | None = None,
        task_description: str | None = None,
        hypothesis_id: str | None = None,
        iteration: int | None = None
    ) -> None:
        """Log a successful citation verification.

        Args:
            result: The verification result showing success
            agent_name: Name of the agent that generated the text
            task_description: Description of the task being performed
            hypothesis_id: ID of the hypothesis being processed
            iteration: Research iteration number
        """
        if not result.is_supported:
            return  # Not a success

        context = {
            "agent_name": agent_name,
            "task_description": task_description,
            "hypothesis_id": hypothesis_id,
            "iteration": iteration,
            "event_type": "citation_verification_success"
        }

        entry = self._create_base_entry(result, context)

        # Add success-specific information
        entry["success_details"] = {
            "verified_citations": [
                {
                    "paper_id": match.paper_id,
                    "paper_title": match.paper_title,
                    "match_score": match.match_score,
                    "match_reasons": match.match_reasons
                }
                for match in result.matches
            ]
        }

        self._write_log_entry(self.success_log, entry)

    def log_retry_attempt(
        self,
        original_result: VerificationResult,
        retry_attempt: int,
        retry_strategy: str,
        new_text: str | None = None,
        agent_name: str | None = None,
        hypothesis_id: str | None = None
    ) -> None:
        """Log a citation fix retry attempt.

        Args:
            original_result: The original failed verification result
            retry_attempt: Attempt number (1, 2, 3, etc.)
            retry_strategy: Strategy used for this retry
            new_text: Modified text for this attempt (if applicable)
            agent_name: Name of the agent performing the retry
            hypothesis_id: ID of the hypothesis being retried
        """
        context = {
            "agent_name": agent_name,
            "hypothesis_id": hypothesis_id,
            "event_type": "citation_retry_attempt"
        }

        entry = self._create_base_entry(original_result, context)

        # Add retry-specific information
        entry["retry_details"] = {
            "attempt_number": retry_attempt,
            "retry_strategy": retry_strategy,
            "new_text": new_text,
            "original_failure_reason": original_result.reason
        }

        self._write_log_entry(self.retry_log, entry)

    def log_final_status(
        self,
        final_result: VerificationResult,
        original_result: VerificationResult,
        total_attempts: int,
        final_status: str,  # "success" | "failure" | "abandoned"
        agent_name: str | None = None,
        hypothesis_id: str | None = None
    ) -> None:
        """Log the final outcome after all retry attempts.

        Args:
            final_result: The final verification result
            original_result: The original failed result
            total_attempts: Total number of attempts made
            final_status: Final outcome status
            agent_name: Name of the agent
            hypothesis_id: ID of the hypothesis
        """
        if final_status == "success":
            self.log_citation_success(
                final_result,
                agent_name=agent_name,
                task_description=f"Citation fix after {total_attempts} attempts",
                hypothesis_id=hypothesis_id
            )
        else:
            # Log as failure with retry summary
            context = {
                "agent_name": agent_name,
                "hypothesis_id": hypothesis_id,
                "event_type": "citation_final_failure"
            }

            entry = self._create_base_entry(final_result, context)
            entry["final_failure_details"] = {
                "total_attempts": total_attempts,
                "final_status": final_status,
                "original_failure": original_result.reason,
                "final_failure": final_result.reason
            }

            self._write_log_entry(self.failure_log, entry)

    def _suggest_fix_action(self, result: VerificationResult) -> str:
        """Suggest an action to fix the citation failure."""
        if result.missing_citations and result.available_but_unused:
            return f"Add citations to {len(result.available_but_unused)} available supporting papers"
        elif result.existing_citations and not result.matches:
            return "Replace invalid citations with appropriate references"
        elif not result.available_but_unused:
            return "No supporting literature available - consider rephrasing claim or gathering more references"
        else:
            return "Review claim and citation requirements"

    def get_failure_statistics(self, days: int = 30) -> dict[str, Any]:
        """Get statistics about citation failures over the specified period.

        Args:
            days: Number of days back to analyze

        Returns:
            Dictionary with failure statistics
        """
        cutoff_date = datetime.utcnow().replace(microsecond=0)
        cutoff_timestamp = (cutoff_date.timestamp() - (days * 24 * 3600))

        stats = {
            "total_failures": 0,
            "failures_by_type": {},
            "failures_by_agent": {},
            "common_failure_reasons": {},
            "avg_available_references": 0,
            "period_days": days
        }

        if not self.failure_log.exists():
            return stats

        total_available_refs = 0

        try:
            with open(self.failure_log, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))

                        if entry_time.timestamp() >= cutoff_timestamp:
                            stats["total_failures"] += 1

                            # Count by claim type
                            claim_type = entry.get("claim_type", "unknown")
                            stats["failures_by_type"][claim_type] = stats["failures_by_type"].get(claim_type, 0) + 1

                            # Count by agent
                            agent = entry.get("context", {}).get("agent_name", "unknown")
                            stats["failures_by_agent"][agent] = stats["failures_by_agent"].get(agent, 0) + 1

                            # Count failure reasons
                            reason = entry.get("verification_result", {}).get("reason", "unknown")
                            stats["common_failure_reasons"][reason] = stats["common_failure_reasons"].get(reason, 0) + 1

                            # Track available references
                            available_count = entry.get("verification_result", {}).get("available_unused_count", 0)
                            total_available_refs += available_count

                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue  # Skip malformed entries

        except FileNotFoundError:
            pass

        if stats["total_failures"] > 0:
            stats["avg_available_references"] = total_available_refs / stats["total_failures"]

        return stats