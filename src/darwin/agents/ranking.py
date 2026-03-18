"""Ranking agent — Elo K=32 pairwise tournament to sort hypotheses."""
from __future__ import annotations

from itertools import combinations

import anthropic

from darwin.agents._common import latest_hypotheses, parse_json_response
from darwin.config import TOP_N_HYPOTHESES
from darwin.state import Hypothesis, ResearchState

_K = 32.0

_SYSTEM = """\
You are a scientific judge comparing two research hypotheses.
Given a topic and two hypotheses (A and B), decide which is scientifically stronger.

Output a JSON object with one key:
  "winner": "a", "b", or "draw"

Criteria: novelty, testability, specificity, scientific merit.
Output ONLY valid JSON — no prose, no markdown fences."""


def _elo_update(
    ra: float, rb: float, winner: str
) -> tuple[float, float]:
    """Apply one Elo update. winner must be 'a', 'b', or 'draw'."""
    ea = 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))
    eb = 1.0 - ea
    if winner == "a":
        sa, sb = 1.0, 0.0
    elif winner == "b":
        sa, sb = 0.0, 1.0
    else:
        sa, sb = 0.5, 0.5
    return ra + _K * (sa - ea), rb + _K * (sb - eb)


def run(state: ResearchState) -> dict[str, object]:
    """Run Elo K=32 pairwise tournament and populate ranked_ids / top_hypotheses."""
    client = anthropic.Anthropic()

    pool = latest_hypotheses(state["hypotheses"])
    if not pool:
        return {
            "ranked_ids": [],
            "top_hypotheses": [],
            "messages": [{"role": "agent", "agent": "ranking", "content": "no hypotheses to rank"}],
        }

    # Seed Elo ratings from existing scores (scaled to 800–1200 range)
    ratings: dict[str, float] = {h["id"]: 800.0 + h["score"] * 400.0 for h in pool}

    # Pairwise tournament — ask LLM to judge each pair
    pairs = list(combinations(pool, 2))
    for ha, hb in pairs:
        prompt = (
            f"Topic: {state['topic']}\n\n"
            f"Hypothesis A: {ha['text']}\n\n"
            f"Hypothesis B: {hb['text']}"
        )
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=64,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        result: dict[str, str] = parse_json_response(message)  # type: ignore[assignment]
        winner = result.get("winner", "draw")
        ratings[ha["id"]], ratings[hb["id"]] = _elo_update(
            ratings[ha["id"]], ratings[hb["id"]], winner
        )

    # Normalise ratings back to 0.0–1.0 score
    if len(ratings) > 1:
        min_r = min(ratings.values())
        max_r = max(ratings.values())
        span = max_r - min_r or 1.0
        norm: dict[str, float] = {hid: (r - min_r) / span for hid, r in ratings.items()}
    else:
        norm = {hid: 0.5 for hid in ratings}

    sorted_pool = sorted(pool, key=lambda h: ratings[h["id"]], reverse=True)
    ranked_ids = [h["id"] for h in sorted_pool]

    # Return updated hypotheses with new scores appended
    updated: list[Hypothesis] = [
        Hypothesis(
            id=h["id"],
            text=h["text"],
            score=norm[h["id"]],
            reflections=h["reflections"],
            generation=h["generation"],
            evolved_from=h["evolved_from"],
        )
        for h in sorted_pool
    ]

    top = updated[:TOP_N_HYPOTHESES]

    return {
        "hypotheses": updated,
        "ranked_ids": ranked_ids,
        "top_hypotheses": top,
        "messages": [
            {
                "role": "agent",
                "agent": "ranking",
                "content": (
                    f"Ranked {len(pool)} hypotheses via Elo tournament "
                    f"({len(pairs)} comparisons); top: {ranked_ids[:3]}"
                ),
            }
        ],
    }
