#!/usr/bin/env uv run python
"""Test to verify iteration 2 performance fix."""
from unittest.mock import MagicMock, patch
import json

from darwin.agents import ranking
from darwin.state import Hypothesis, ResearchState


def _make_hypothesis(id: str, score: float = 0.5, generation: int = 1) -> Hypothesis:
    return {
        "id": id,
        "text": f"Hypothesis {id}: Test hypothesis text",
        "score": score,
        "reflections": [],
        "generation": generation,
        "evolved_from": None,
        "references": []
    }


def _make_state(**kwargs) -> ResearchState:
    defaults: ResearchState = {
        "topic": "Test iteration 2 performance",
        "max_iterations": 5,
        "iteration": 2,
        "hypotheses": [],
        "ranked_ids": [],
        "top_hypotheses": [],
        "proximity_clusters": [],
        "supervisor_decision": "continue",
        "meta_review_notes": "",
        "human_feedback": None,
        "final_hypotheses": [],
        "messages": [],
        "literature_context": []
    }
    defaults.update(kwargs)  # type: ignore[typeddict-item]
    return defaults


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = [MagicMock(type="text", text=text[1:] if text else text)]
    return msg


def test_iteration2_uses_batch_optimization():
    """Test that iteration 2 (13 hypotheses) now uses batch comparisons instead of pairwise."""
    # Simulate iteration 2: 5 original + 8 more = 13 hypotheses
    hyps = [_make_hypothesis(f"h{i}") for i in range(13)]

    # Mock batch comparison responses
    batch_payload = json.dumps({"ranking": ["a", "b", "c", "d"]})

    with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_message(batch_payload)
        result = ranking.run(_make_state(hypotheses=hyps))

    # Should now use batch comparisons instead of pairwise tournament
    message_content = result["messages"][0]["content"]
    assert "batch comparisons" in message_content, f"Expected batch comparisons, got: {message_content}"

    # Calculate expected efficiency improvement
    # Previous: 13 hypotheses = 78 pairwise comparisons (13 * 12 / 2)
    # New: batch comparison should be much more efficient
    print(f"✓ Iteration 2 simulation (13 hypotheses): {message_content}")

    # Verify it's not using expensive pairwise tournament
    assert "pairwise tournament" not in message_content, "Should not fall back to pairwise tournament"

    # Should show significant reduction vs full pairwise
    assert "78 full pairwise" in message_content, "Should show comparison vs full pairwise"


def test_boundary_conditions():
    """Test threshold boundary conditions."""
    test_cases = [
        (11, "pairwise tournament"),  # Just below threshold
        (12, "batch comparisons"),    # At threshold
        (13, "batch comparisons"),    # Iteration 2 case
        (24, "batch comparisons"),    # Just below Swiss threshold
        (25, "Swiss tournament"),     # At Swiss threshold
        (30, "Swiss tournament"),     # Above Swiss threshold
    ]

    for n, expected_strategy in test_cases:
        hyps = [_make_hypothesis(f"h{i}") for i in range(n)]

        if expected_strategy == "pairwise tournament":
            payload = json.dumps({"winner": "a"})
        elif expected_strategy == "batch comparisons":
            payload = json.dumps({"ranking": ["a", "b", "c", "d"]})
        else:  # Swiss tournament
            payload = json.dumps({"winner": "a"})

        with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = ranking.run(_make_state(hypotheses=hyps))

        message_content = result["messages"][0]["content"]
        assert expected_strategy in message_content, f"For {n} hypotheses, expected {expected_strategy}, got: {message_content}"
        print(f"✓ {n} hypotheses → {expected_strategy}")


if __name__ == "__main__":
    print("Testing iteration 2 performance fix...")
    test_iteration2_uses_batch_optimization()
    print()
    print("Testing threshold boundary conditions...")
    test_boundary_conditions()
    print("\n✓ All iteration 2 performance tests passed!")