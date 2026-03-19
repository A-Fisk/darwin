"""Tests for the reflection agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from darwin.agents import reflection
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


def _hyp(id: str = "aaa", generation: int = 1, score: float = 0.5) -> Hypothesis:
    return Hypothesis(id=id, text="some hypothesis", score=score,
                      reflections=[], generation=generation, evolved_from=None)


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    # Agents use assistant prefill, so the model returns text AFTER the first character
    msg.content = [MagicMock(type="text", text=text[1:] if text else text)]
    return msg


class TestReflectionRun:
    def test_returns_messages_on_empty_current_iteration(self) -> None:
        # hypotheses exist but from a different iteration
        old_hyp = _hyp(id="old", generation=0)
        result = reflection.run(_make_state(hypotheses=[old_hyp], iteration=1))
        assert "messages" in result
        assert "hypotheses" not in result

    def test_returns_updated_hypotheses(self) -> None:
        hyp = _hyp(id="h1", generation=1)
        payload = json.dumps({"critique": "good hypothesis", "score": 0.9})
        with patch("darwin.agents.reflection.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = reflection.run(_make_state(hypotheses=[hyp], iteration=1))

        assert "hypotheses" in result
        updated = result["hypotheses"]  # type: ignore[index]
        assert len(updated) == 1
        assert updated[0]["score"] == pytest.approx(0.9)
        assert "good hypothesis" in updated[0]["reflections"]

    def test_appends_critique_to_reflections(self) -> None:
        hyp = Hypothesis(id="h1", text="text", score=0.5,
                         reflections=["prior critique"], generation=1, evolved_from=None)
        payload = json.dumps({"critique": "new critique", "score": 0.7})
        with patch("darwin.agents.reflection.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = reflection.run(_make_state(hypotheses=[hyp], iteration=1))

        updated = result["hypotheses"][0]  # type: ignore[index]
        assert "prior critique" in updated["reflections"]
        assert "new critique" in updated["reflections"]

    def test_malformed_json_raises(self) -> None:
        hyp = _hyp(id="h1", generation=1)
        with patch("darwin.agents.reflection.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message("not json {{")
            with pytest.raises(json.JSONDecodeError):
                reflection.run(_make_state(hypotheses=[hyp], iteration=1))

    def test_missing_score_defaults_to_0_5(self) -> None:
        hyp = _hyp(id="h1", generation=1)
        payload = json.dumps({"critique": "ok"})  # no "score" key
        with patch("darwin.agents.reflection.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = reflection.run(_make_state(hypotheses=[hyp], iteration=1))

        updated = result["hypotheses"][0]  # type: ignore[index]
        assert updated["score"] == pytest.approx(0.5)

    def test_missing_critique_defaults_to_empty_string(self) -> None:
        hyp = _hyp(id="h1", generation=1)
        payload = json.dumps({"score": 0.8})  # no "critique" key
        with patch("darwin.agents.reflection.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = reflection.run(_make_state(hypotheses=[hyp], iteration=1))

        updated = result["hypotheses"][0]  # type: ignore[index]
        assert "" in updated["reflections"]

    def test_only_reflects_on_current_iteration(self) -> None:
        hyp_old = _hyp(id="old", generation=0)
        hyp_new = _hyp(id="new", generation=1)
        payload = json.dumps({"critique": "critique", "score": 0.6})
        with patch("darwin.agents.reflection.anthropic.Anthropic") as MockClient:
            mock_create = MockClient.return_value.messages.create
            mock_create.return_value = _mock_message(payload)
            result = reflection.run(_make_state(hypotheses=[hyp_old, hyp_new], iteration=1))

        # Only 1 call (for hyp_new), not 2
        assert mock_create.call_count == 1
        assert len(result["hypotheses"]) == 1  # type: ignore[arg-type]
        assert result["hypotheses"][0]["id"] == "new"  # type: ignore[index]
