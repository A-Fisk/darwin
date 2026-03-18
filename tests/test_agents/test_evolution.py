"""Tests for the evolution agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from darwin.agents import evolution
from darwin.state import Hypothesis, ResearchState


def _make_state(**kwargs) -> ResearchState:
    defaults: ResearchState = {
        "topic": "test topic",
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
    }
    defaults.update(kwargs)  # type: ignore[typeddict-item]
    return defaults


def _hyp(id: str = "aaa", score: float = 0.8) -> Hypothesis:
    return Hypothesis(id=id, text=f"hyp {id}", score=score,
                      reflections=["good"], generation=1, evolved_from=None)


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = [MagicMock(type="text", text=text)]
    return msg


class TestEvolutionRun:
    def test_no_top_hypotheses_returns_empty(self) -> None:
        result = evolution.run(_make_state(top_hypotheses=[]))
        assert result["hypotheses"] == []

    def test_returns_expected_keys(self) -> None:
        parents = [_hyp("p1"), _hyp("p2")]
        from darwin.config import EVOLVED_PER_ITERATION
        items = [{"text": f"evolved {i}", "parent_id": "p1"} for i in range(EVOLVED_PER_ITERATION)]
        payload = json.dumps(items)
        with patch("darwin.agents.evolution.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = evolution.run(_make_state(top_hypotheses=parents))

        assert "hypotheses" in result
        assert "messages" in result

    def test_generates_evolved_per_iteration_count(self) -> None:
        from darwin.config import EVOLVED_PER_ITERATION
        parents = [_hyp("p1")]
        items = [{"text": f"evolved {i}", "parent_id": "p1"} for i in range(EVOLVED_PER_ITERATION)]
        payload = json.dumps(items)
        with patch("darwin.agents.evolution.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = evolution.run(_make_state(top_hypotheses=parents))

        assert len(result["hypotheses"]) == EVOLVED_PER_ITERATION  # type: ignore[arg-type]

    def test_evolved_hypothesis_has_parent_id(self) -> None:
        parents = [_hyp("p1")]
        items = [{"text": "child hyp", "parent_id": "p1"}]
        payload = json.dumps(items)
        with patch("darwin.agents.evolution.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = evolution.run(_make_state(top_hypotheses=parents))

        evolved_hyp = result["hypotheses"][0]  # type: ignore[index]
        assert evolved_hyp["evolved_from"] == "p1"

    def test_invalid_parent_id_falls_back_to_first_parent(self) -> None:
        parents = [_hyp("p1"), _hyp("p2")]
        items = [{"text": "child hyp", "parent_id": "nonexistent_id"}]
        payload = json.dumps(items)
        with patch("darwin.agents.evolution.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = evolution.run(_make_state(top_hypotheses=parents))

        evolved_hyp = result["hypotheses"][0]  # type: ignore[index]
        assert evolved_hyp["evolved_from"] == "p1"  # fallback to first parent

    def test_evolved_hypothesis_initial_score_is_0_5(self) -> None:
        parents = [_hyp("p1")]
        items = [{"text": "child hyp", "parent_id": "p1"}]
        payload = json.dumps(items)
        with patch("darwin.agents.evolution.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = evolution.run(_make_state(top_hypotheses=parents))

        assert result["hypotheses"][0]["score"] == 0.5  # type: ignore[index]

    def test_evolved_hypothesis_has_current_iteration(self) -> None:
        parents = [_hyp("p1")]
        items = [{"text": "child hyp", "parent_id": "p1"}]
        payload = json.dumps(items)
        with patch("darwin.agents.evolution.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = evolution.run(_make_state(top_hypotheses=parents, iteration=3))

        assert result["hypotheses"][0]["generation"] == 3  # type: ignore[index]

    def test_malformed_json_raises(self) -> None:
        parents = [_hyp("p1")]
        with patch("darwin.agents.evolution.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message("bad json [")
            with pytest.raises(json.JSONDecodeError):
                evolution.run(_make_state(top_hypotheses=parents))

    def test_truncates_to_evolved_per_iteration(self) -> None:
        from darwin.config import EVOLVED_PER_ITERATION
        parents = [_hyp("p1")]
        # API returns more than expected
        items = [
            {"text": f"evolved {i}", "parent_id": "p1"} for i in range(EVOLVED_PER_ITERATION + 5)
        ]
        payload = json.dumps(items)
        with patch("darwin.agents.evolution.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = evolution.run(_make_state(top_hypotheses=parents))

        assert len(result["hypotheses"]) == EVOLVED_PER_ITERATION  # type: ignore[arg-type]
