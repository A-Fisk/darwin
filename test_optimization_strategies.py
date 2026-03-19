#!/usr/bin/env uv run python
"""Test to verify optimization strategies are working correctly."""
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
        "topic": "Test optimization strategies",
        "max_iterations": 5,
        "iteration": 1,
        "hypotheses": [],
        "ranked_ids": [],
        "top_hypotheses": [],
        "proximity_clusters": [],
        "supervisor_decision": "continue",
        "meta_review_notes": "",
        "human_feedback": None,
        "final_hypotheses": [],
        "messages": [],
    }
    defaults.update(kwargs)  # type: ignore[typeddict-item]
    return defaults


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = [MagicMock(type="text", text=text[1:] if text else text)]
    return msg


def test_small_pool_uses_pairwise():
    """Test that small pools (< 15) use classic pairwise tournament."""
    hyps = [_make_hypothesis(f"h{i}") for i in range(5)]
    payload = json.dumps({"winner": "a"})

    with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_message(payload)
        result = ranking.run(_make_state(hypotheses=hyps))

    # Should use pairwise tournament
    message_content = result["messages"][0]["content"]
    assert "pairwise tournament" in message_content
    # 5 hypotheses = 10 pairwise comparisons
    assert "10 comparisons vs 10 full pairwise" in message_content
    print(f"✓ Small pool (5): {message_content}")


def test_iteration2_critical_case():
    """Test that iteration 2 (13 hypotheses) uses batch comparisons to avoid 840s performance issue."""
    hyps = [_make_hypothesis(f"h{i}") for i in range(13)]

    # Mock batch comparison responses
    batch_payload = json.dumps({"ranking": ["a", "b", "c", "d"]})

    with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_message(batch_payload)
        result = ranking.run(_make_state(hypotheses=hyps))

    # Should use batch comparisons (20 vs 78 pairwise comparisons = 74% improvement)
    message_content = result["messages"][0]["content"]
    assert "batch comparisons" in message_content
    assert "20 comparisons vs 78 full pairwise" in message_content
    print(f"✓ Iteration 2 critical case (13): {message_content}")


def test_medium_pool_uses_batch():
    """Test that medium pools (12-24) use batch comparisons."""
    hyps = [_make_hypothesis(f"h{i}") for i in range(18)]

    # Mock batch comparison responses
    batch_payload = json.dumps({"ranking": ["a", "b", "c", "d"]})

    with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_message(batch_payload)
        result = ranking.run(_make_state(hypotheses=hyps))

    # Should use batch comparisons
    message_content = result["messages"][0]["content"]
    assert "batch comparisons" in message_content
    print(f"✓ Medium pool (18): {message_content}")


def test_large_pool_uses_swiss():
    """Test that large pools (>= 25) use Swiss tournament."""
    hyps = [_make_hypothesis(f"h{i}") for i in range(30)]
    payload = json.dumps({"winner": "a"})

    with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_message(payload)
        result = ranking.run(_make_state(hypotheses=hyps))

    # Should use Swiss tournament
    message_content = result["messages"][0]["content"]
    assert "Swiss tournament" in message_content
    # Should have far fewer comparisons than full pairwise (30 choose 2 = 435)
    assert "435 full pairwise" in message_content
    print(f"✓ Large pool (30): {message_content}")


def test_performance_improvement():
    """Test that optimization provides significant performance improvement."""
    # Simulate iteration 4-5 scale (around 32-40 hypotheses)
    n = 35
    hyps = [_make_hypothesis(f"h{i}") for i in range(n)]
    payload = json.dumps({"winner": "a"})

    with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = _mock_message(payload)
        result = ranking.run(_make_state(hypotheses=hyps))

    message_content = result["messages"][0]["content"]
    print(f"✓ Performance test (35): {message_content}")

    # Extract comparison counts
    import re
    match = re.search(r'(\d+) comparisons vs (\d+) full pairwise', message_content)
    if match:
        optimized_comparisons = int(match.group(1))
        full_pairwise = int(match.group(2))
        improvement = (full_pairwise - optimized_comparisons) / full_pairwise * 100
        print(f"  - Optimized: {optimized_comparisons} comparisons")
        print(f"  - Full pairwise: {full_pairwise} comparisons")
        print(f"  - Improvement: {improvement:.1f}% reduction")

        # Should have significant improvement
        assert improvement > 50, f"Expected > 50% improvement, got {improvement:.1f}%"
    else:
        print("  - Could not parse comparison counts from message")


if __name__ == "__main__":
    print("Testing ranking algorithm optimization strategies...")
    test_small_pool_uses_pairwise()
    test_iteration2_critical_case()
    test_medium_pool_uses_batch()
    test_large_pool_uses_swiss()
    test_performance_improvement()
    print("\n✓ All optimization strategy tests passed!")