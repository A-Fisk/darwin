"""Tests for the proximity (clustering) agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from darwin.agents import proximity
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


def _hyp(id: str) -> Hypothesis:
    return Hypothesis(id=id, text=f"hyp {id}", score=0.5,
                      reflections=[], generation=1, evolved_from=None)


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    # Agents use assistant prefill, so the model returns text AFTER the first character
    msg.content = [MagicMock(type="text", text=text[1:] if text else text)]
    return msg


class TestProximityRun:
    def test_empty_pool_returns_empty_clusters(self) -> None:
        result = proximity.run(_make_state(hypotheses=[]))
        assert result["proximity_clusters"] == []

    def test_returns_expected_keys(self) -> None:
        hyps = [_hyp("a"), _hyp("b")]
        payload = json.dumps([["a", "b"]])
        with patch("darwin.agents.proximity.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = proximity.run(_make_state(hypotheses=hyps))

        assert "proximity_clusters" in result
        assert "messages" in result

    def test_clusters_contain_all_ids(self) -> None:
        hyps = [_hyp("a"), _hyp("b"), _hyp("c")]
        payload = json.dumps([["a"], ["b", "c"]])
        with patch("darwin.agents.proximity.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = proximity.run(_make_state(hypotheses=hyps))

        clusters = result["proximity_clusters"]  # type: ignore[union-attr]
        all_ids = {hid for cluster in clusters for hid in cluster}
        assert all_ids == {"a", "b", "c"}

    def test_unclustered_ids_appended(self) -> None:
        """If API omits some IDs, they should be appended in a new cluster."""
        hyps = [_hyp("a"), _hyp("b"), _hyp("c")]
        # API only clusters a and b, omitting c
        payload = json.dumps([["a", "b"]])
        with patch("darwin.agents.proximity.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = proximity.run(_make_state(hypotheses=hyps))

        clusters = result["proximity_clusters"]  # type: ignore[union-attr]
        all_ids = {hid for cluster in clusters for hid in cluster}
        assert "c" in all_ids  # c rescued into new cluster

    def test_cluster_count_matches_llm_output(self) -> None:
        hyps = [_hyp("a"), _hyp("b"), _hyp("c"), _hyp("d")]
        payload = json.dumps([["a", "b"], ["c", "d"]])
        with patch("darwin.agents.proximity.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = proximity.run(_make_state(hypotheses=hyps))

        assert len(result["proximity_clusters"]) == 2  # type: ignore[arg-type]

    def test_malformed_json_raises(self) -> None:
        hyps = [_hyp("a"), _hyp("b")]
        with patch("darwin.agents.proximity.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message("invalid {{")
            with pytest.raises(json.JSONDecodeError):
                proximity.run(_make_state(hypotheses=hyps))

    def test_deduplication_via_latest_hypotheses(self) -> None:
        """Latest version of duplicate IDs should be used."""
        hyp_v1 = Hypothesis(id="dup", text="v1", score=0.3,
                            reflections=[], generation=1, evolved_from=None)
        hyp_v2 = Hypothesis(id="dup", text="v2", score=0.7,
                            reflections=[], generation=1, evolved_from=None)
        payload = json.dumps([["dup"]])
        with patch("darwin.agents.proximity.anthropic.Anthropic") as MockClient:
            mock_create = MockClient.return_value.messages.create
            mock_create.return_value = _mock_message(payload)
            result = proximity.run(_make_state(hypotheses=[hyp_v1, hyp_v2]))

        # Should still work without error; deduplicated pool has 1 item
        clusters = result["proximity_clusters"]  # type: ignore[union-attr]
        all_ids = [hid for cluster in clusters for hid in cluster]
        assert all_ids.count("dup") == 1
