"""Tests for the generation agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from darwin.agents import generation
from darwin.state import Hypothesis, ResearchState


def _make_state(**kwargs) -> ResearchState:
    defaults: ResearchState = {
        "topic": "test topic",
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
    msg.content = [MagicMock(type="text", text=text)]
    return msg


class TestGenerationRun:
    def test_returns_hypotheses_and_messages(self) -> None:
        payload = json.dumps([{"text": "hyp A"}, {"text": "hyp B"}, {"text": "hyp C"},
                               {"text": "hyp D"}, {"text": "hyp E"}])
        with patch("darwin.agents.generation.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = generation.run(_make_state())

        assert "hypotheses" in result
        assert "messages" in result

    def test_generates_expected_count(self) -> None:
        from darwin.config import NEW_PER_ITERATION
        items = [{"text": f"hyp {i}"} for i in range(NEW_PER_ITERATION)]
        payload = json.dumps(items)
        with patch("darwin.agents.generation.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = generation.run(_make_state())

        assert len(result["hypotheses"]) == NEW_PER_ITERATION  # type: ignore[arg-type]

    def test_hypothesis_structure(self) -> None:
        payload = json.dumps([{"text": "interesting idea"}])
        with patch("darwin.agents.generation.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = generation.run(_make_state())

        hyp = result["hypotheses"][0]  # type: ignore[index]
        assert "id" in hyp
        assert "text" in hyp
        assert hyp["text"] == "interesting idea"
        assert hyp["score"] == 0.5
        assert hyp["reflections"] == []
        assert hyp["generation"] == 1
        assert hyp["evolved_from"] is None

    def test_truncates_to_new_per_iteration(self) -> None:
        from darwin.config import NEW_PER_ITERATION
        # API returns more than expected — should truncate
        items = [{"text": f"hyp {i}"} for i in range(NEW_PER_ITERATION + 5)]
        payload = json.dumps(items)
        with patch("darwin.agents.generation.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = generation.run(_make_state())

        assert len(result["hypotheses"]) == NEW_PER_ITERATION  # type: ignore[arg-type]

    def test_malformed_json_raises(self) -> None:
        with patch("darwin.agents.generation.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message("not json")
            with pytest.raises(json.JSONDecodeError):
                generation.run(_make_state())

    def test_empty_json_array_returns_no_hypotheses(self) -> None:
        with patch("darwin.agents.generation.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message("[]")
            result = generation.run(_make_state())

        assert result["hypotheses"] == []  # type: ignore[comparison-overlap]

    def test_existing_hypotheses_included_in_context(self) -> None:
        """Existing hypotheses should be sent as context to avoid repetition."""
        existing: list[Hypothesis] = [
            Hypothesis(id="abc", text="prior hyp", score=0.8,
                       reflections=[], generation=0, evolved_from=None)
        ]
        payload = json.dumps([{"text": "new hyp"}])
        with patch("darwin.agents.generation.anthropic.Anthropic") as MockClient:
            mock_create = MockClient.return_value.messages.create
            mock_create.return_value = _mock_message(payload)
            generation.run(_make_state(hypotheses=existing))

            call_kwargs = mock_create.call_args
            # The user message content should reference "prior hyp"
            user_msg = call_kwargs[1]["messages"][0]["content"]
            assert "prior hyp" in user_msg
