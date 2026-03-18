"""Tests for the supervisor agent (routing decisions)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from darwin.agents import supervisor
from darwin.agents.supervisor import route
from darwin.state import Hypothesis, ResearchState


def _make_state(**kwargs) -> ResearchState:
    defaults: ResearchState = {
        "topic": "test topic",
        "max_iterations": 5,
        "iteration": 0,
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


def _hyp(id: str, score: float = 0.8) -> Hypothesis:
    return Hypothesis(id=id, text=f"hyp {id}", score=score,
                      reflections=[], generation=1, evolved_from=None)


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    return msg


class TestSupervisorRun:
    def test_iteration_0_skips_llm_and_increments(self) -> None:
        result = supervisor.run(_make_state(iteration=0))
        assert result["iteration"] == 1
        assert "messages" in result

    def test_iteration_0_no_api_call(self) -> None:
        with patch("darwin.agents.supervisor.anthropic.Anthropic") as MockClient:
            supervisor.run(_make_state(iteration=0))
            MockClient.return_value.messages.create.assert_not_called()

    def test_increments_iteration(self) -> None:
        payload = json.dumps({"decision": "continue"})
        with patch("darwin.agents.supervisor.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = supervisor.run(_make_state(iteration=2))

        assert result["iteration"] == 3

    def test_returns_supervisor_decision(self) -> None:
        payload = json.dumps({"decision": "stop"})
        with patch("darwin.agents.supervisor.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = supervisor.run(_make_state(iteration=1))

        assert result["supervisor_decision"] == "stop"

    def test_invalid_decision_falls_back_to_prior(self) -> None:
        payload = json.dumps({"decision": "nonsense"})
        with patch("darwin.agents.supervisor.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = supervisor.run(_make_state(iteration=1, supervisor_decision="continue"))

        assert result["supervisor_decision"] == "continue"

    def test_human_review_decision_preserved(self) -> None:
        payload = json.dumps({"decision": "human_review"})
        with patch("darwin.agents.supervisor.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = supervisor.run(_make_state(iteration=2))

        assert result["supervisor_decision"] == "human_review"

    def test_malformed_json_raises(self) -> None:
        with patch("darwin.agents.supervisor.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message("not json")
            with pytest.raises(json.JSONDecodeError):
                supervisor.run(_make_state(iteration=1))

    def test_returns_messages(self) -> None:
        payload = json.dumps({"decision": "continue"})
        with patch("darwin.agents.supervisor.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = supervisor.run(_make_state(iteration=1))

        assert "messages" in result
        assert len(result["messages"]) == 1


class TestSupervisorRoute:
    def test_continue_decision_routes_to_generate(self) -> None:
        state = _make_state(iteration=2, max_iterations=5, supervisor_decision="continue")
        assert route(state) == "generate"

    def test_stop_decision_routes_to_end(self) -> None:
        state = _make_state(iteration=2, max_iterations=5, supervisor_decision="stop")
        assert route(state) == "end"

    def test_human_review_decision_routes_to_human_review(self) -> None:
        state = _make_state(iteration=2, max_iterations=5, supervisor_decision="human_review")
        assert route(state) == "human_review"

    def test_exceeded_max_iterations_routes_to_end(self) -> None:
        # iteration > max_iterations
        state = _make_state(iteration=6, max_iterations=5, supervisor_decision="continue")
        assert route(state) == "end"

    def test_exactly_at_max_iterations_continues(self) -> None:
        # iteration == max_iterations should still generate
        state = _make_state(iteration=5, max_iterations=5, supervisor_decision="continue")
        assert route(state) == "generate"

    def test_default_decision_is_generate(self) -> None:
        """Missing supervisor_decision key should default to continue → generate."""
        state = _make_state(iteration=1, max_iterations=5)
        # supervisor_decision defaults to "continue" in _make_state
        assert route(state) == "generate"
