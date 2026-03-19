"""Tests for the ranking agent (Elo K=32 pairwise tournament)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from darwin.agents import ranking
from darwin.agents.ranking import _elo_update
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


def _hyp(id: str, score: float = 0.5, generation: int = 1) -> Hypothesis:
    return Hypothesis(id=id, text=f"hyp {id}", score=score,
                      reflections=[], generation=generation, evolved_from=None)


def _mock_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    # Ranking agent uses prefill "{", so Claude response doesn't include the opening brace
    msg.content = [MagicMock(type="text", text=text[1:] if text else text)]
    return msg


class TestEloUpdate:
    def test_winner_a_increases_a_rating(self) -> None:
        ra, rb = 1000.0, 1000.0
        new_ra, new_rb = _elo_update(ra, rb, "a")
        assert new_ra > ra
        assert new_rb < rb

    def test_winner_b_increases_b_rating(self) -> None:
        ra, rb = 1000.0, 1000.0
        new_ra, new_rb = _elo_update(ra, rb, "b")
        assert new_ra < ra
        assert new_rb > rb

    def test_draw_minimal_change(self) -> None:
        ra, rb = 1000.0, 1000.0
        new_ra, new_rb = _elo_update(ra, rb, "draw")
        assert new_ra == pytest.approx(ra, abs=1e-6)
        assert new_rb == pytest.approx(rb, abs=1e-6)

    def test_k32_magnitude(self) -> None:
        """Equal ratings: win should change by K/2 = 16."""
        ra, rb = 1000.0, 1000.0
        new_ra, _ = _elo_update(ra, rb, "a")
        assert new_ra == pytest.approx(1016.0, abs=0.01)

    def test_ratings_sum_conserved(self) -> None:
        ra, rb = 1200.0, 800.0
        new_ra, new_rb = _elo_update(ra, rb, "b")
        assert new_ra + new_rb == pytest.approx(ra + rb, abs=1e-9)


class TestRankingRun:
    def test_empty_pool_returns_empty_ranked_ids(self) -> None:
        result = ranking.run(_make_state(hypotheses=[]))
        assert result["ranked_ids"] == []
        assert result["top_hypotheses"] == []

    def test_returns_expected_keys(self) -> None:
        hyp_a = _hyp("a")
        hyp_b = _hyp("b")
        payload = json.dumps({"winner": "a"})
        with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = ranking.run(_make_state(hypotheses=[hyp_a, hyp_b]))

        assert "ranked_ids" in result
        assert "top_hypotheses" in result
        assert "hypotheses" in result
        assert "messages" in result

    def test_ranked_ids_contains_all_hypothesis_ids(self) -> None:
        hyps = [_hyp(id) for id in ["x", "y", "z"]]
        payload = json.dumps({"winner": "a"})
        with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = ranking.run(_make_state(hypotheses=hyps))

        assert set(result["ranked_ids"]) == {"x", "y", "z"}  # type: ignore[arg-type]

    def test_winner_a_ends_up_higher_ranked(self) -> None:
        """When LLM always picks 'a' as winner, 'a' should be ranked first."""
        hyp_a = _hyp("aa", score=0.5)
        hyp_b = _hyp("bb", score=0.5)
        payload = json.dumps({"winner": "a"})
        with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = ranking.run(_make_state(hypotheses=[hyp_a, hyp_b]))

        assert result["ranked_ids"][0] == "aa"  # type: ignore[index]

    def test_top_hypotheses_capped_at_top_n(self) -> None:
        from darwin.config import TOP_N_HYPOTHESES
        hyps = [_hyp(str(i)) for i in range(TOP_N_HYPOTHESES + 3)]
        payload = json.dumps({"winner": "a"})
        with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            result = ranking.run(_make_state(hypotheses=hyps))

        assert len(result["top_hypotheses"]) == TOP_N_HYPOTHESES  # type: ignore[arg-type]

    def test_scores_normalised_0_to_1(self) -> None:
        hyps = [_hyp("a", score=0.2), _hyp("b", score=0.8), _hyp("c", score=0.5)]
        # Alternate winners to create spread
        side_effects = [
            _mock_message(json.dumps({"winner": "a"})),
            _mock_message(json.dumps({"winner": "a"})),
            _mock_message(json.dumps({"winner": "b"})),
        ]
        with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = side_effects
            result = ranking.run(_make_state(hypotheses=hyps))

        for h in result["hypotheses"]:  # type: ignore[union-attr]
            assert 0.0 <= h["score"] <= 1.0

    def test_malformed_json_raises(self) -> None:
        hyps = [_hyp("a"), _hyp("b")]
        with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message("bad json")
            with pytest.raises(json.JSONDecodeError):
                ranking.run(_make_state(hypotheses=hyps))

    def test_invalid_winner_treated_as_draw(self) -> None:
        """Unknown winner value defaults to draw — should not raise."""
        hyps = [_hyp("a"), _hyp("b")]
        payload = json.dumps({"winner": "invalid_value"})
        with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_message(payload)
            # Should not raise; 'draw' semantics applied
            result = ranking.run(_make_state(hypotheses=hyps))

        # Both end up at roughly equal scores since no real win/loss
        scores = {h["id"]: h["score"] for h in result["hypotheses"]}  # type: ignore[union-attr]
        assert abs(scores["a"] - scores["b"]) < 0.5

    def test_single_hypothesis_no_api_call(self) -> None:
        hyp = _hyp("solo")
        with patch("darwin.agents.ranking.anthropic.Anthropic") as MockClient:
            result = ranking.run(_make_state(hypotheses=[hyp]))
            MockClient.return_value.messages.create.assert_not_called()

        assert result["ranked_ids"] == ["solo"]
