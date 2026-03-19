"""Tests for the meta_review agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from darwin.agents import meta_review
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


def _hyp(id: str, score: float = 0.8) -> Hypothesis:
    return Hypothesis(id=id, text=f"hyp {id}", score=score,
                      reflections=[], generation=1, evolved_from=None)


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    # Agents use assistant prefill, so the model returns text AFTER the first character
    msg.content = [MagicMock(type="text", text=text[1:] if text else text)]
    return msg


class TestMetaReviewRun:
    def test_returns_expected_keys(self) -> None:
        payload = json.dumps({"decision": "continue", "notes": "Looking good."})
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = meta_review.run(_make_state())

        assert "supervisor_decision" in result
        assert "meta_review_notes" in result
        assert "messages" in result

    def test_continue_decision_propagated(self) -> None:
        payload = json.dumps({"decision": "continue", "notes": "Progressing well."})
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = meta_review.run(_make_state())

        assert result["supervisor_decision"] == "continue"

    def test_stop_decision_propagated(self) -> None:
        payload = json.dumps({"decision": "stop", "notes": "Excellent hypotheses."})
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = meta_review.run(_make_state())

        assert result["supervisor_decision"] == "stop"

    def test_human_review_decision_propagated(self) -> None:
        payload = json.dumps({"decision": "human_review", "notes": "Stalled."})
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = meta_review.run(_make_state())

        assert result["supervisor_decision"] == "human_review"

    def test_notes_propagated(self) -> None:
        notes = "Hypotheses show strong convergence across iterations."
        payload = json.dumps({"decision": "continue", "notes": notes})
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = meta_review.run(_make_state())

        assert result["meta_review_notes"] == notes

    def test_invalid_decision_defaults_to_continue(self) -> None:
        payload = json.dumps({"decision": "nonsense", "notes": "oops"})
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = meta_review.run(_make_state())

        assert result["supervisor_decision"] == "continue"

    def test_missing_notes_defaults_to_empty_string(self) -> None:
        payload = json.dumps({"decision": "continue"})  # no "notes" key
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = meta_review.run(_make_state())

        assert result["meta_review_notes"] == ""

    def test_malformed_json_raises(self) -> None:
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message("not json {{")
            with pytest.raises(json.JSONDecodeError):
                meta_review.run(_make_state())

    def test_uses_top_hypotheses_when_available(self) -> None:
        top = [_hyp("t1"), _hyp("t2")]
        pool = [_hyp("p1"), _hyp("p2"), _hyp("p3")] + top
        payload = json.dumps({"decision": "continue", "notes": "ok"})
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            mock_create = MockClient.return_value.messages.create
            mock_create.return_value = _mock_message(payload)
            meta_review.run(_make_state(hypotheses=pool, top_hypotheses=top))

            call_kwargs = mock_create.call_args[1]
            user_msg = call_kwargs["messages"][0]["content"]
            # top hypotheses should appear in the prompt
            assert "t1" in user_msg or "hyp t1" in user_msg

    def test_empty_pool_uses_empty_top_text(self) -> None:
        """With no hypotheses, the agent should still call the LLM without error."""
        payload = json.dumps({"decision": "continue", "notes": "nothing yet"})
        with patch("darwin.agents.meta_review.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = meta_review.run(_make_state(hypotheses=[], top_hypotheses=[]))

        assert result["supervisor_decision"] == "continue"
