"""Ranking agent — Optimized Elo tournament with batching and smart structures."""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from typing import Any

import anthropic

from darwin.agents._common import criteria_prompt_block, latest_hypotheses, parse_json_response
from darwin.config import TOP_N_HYPOTHESES
from darwin.state import Hypothesis, ResearchState

_K = 32.0

# Optimization thresholds
_BATCH_COMPARISON_THRESHOLD = 15  # Use batch comparisons when n >= 15
_SWISS_TOURNAMENT_THRESHOLD = 25  # Use Swiss system when n >= 25
_MAX_BATCH_SIZE = 4  # Maximum hypotheses per batch comparison

_SYSTEM_PAIRWISE = """\
You are a scientific judge comparing two research hypotheses.
Given a topic and two hypotheses (A and B), decide which is scientifically stronger.

Evaluate using these criteria:
{criteria}

When all other criteria are equal, a hypothesis that is grounded in or meaningfully
extends the relevant literature should be preferred over one that is not.

Output a JSON object with one key:
  "winner": "a", "b", or "draw"

Output ONLY valid JSON — no prose, no markdown fences."""

_SYSTEM_BATCH = """\
You are a scientific judge ranking multiple research hypotheses.
Given a topic and {n} hypotheses (A, B, C, etc.), rank them from strongest to weakest.

Evaluate using these criteria:
{criteria}

When all other criteria are equal, a hypothesis that is grounded in or meaningfully
extends the relevant literature should be preferred over one that is not.

Output a JSON object with one key:
  "ranking": ["a", "b", "c", ...] (from strongest to weakest)

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


def _batch_compare_hypotheses(
    client: anthropic.Anthropic,
    batch: list[Hypothesis],
    topic: str,
    criteria_block: str,
    lit_index: dict[str, str]
) -> dict[str, float]:
    """Compare a small batch of hypotheses and return relative strengths."""
    if len(batch) <= 1:
        return {batch[0]["id"]: 0.5} if batch else {}

    # Create batch comparison prompt
    def refs_note(h: Hypothesis) -> str:
        refs = h.get("references", [])
        titles = [lit_index[r] for r in refs if r in lit_index]
        return f" [cites: {'; '.join(titles)}]" if titles else ""

    labels = [chr(ord('A') + i) for i in range(len(batch))]
    hyp_text = "\n\n".join([
        f"Hypothesis {label}: {h['text']}{refs_note(h)}"
        for label, h in zip(labels, batch)
    ])

    prompt = f"Topic: {topic}\n\n{hyp_text}"
    system = _SYSTEM_BATCH.format(n=len(batch), criteria=criteria_block)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    result: dict[str, list[str]] = parse_json_response(message, "{")  # type: ignore[assignment]
    ranking = result.get("ranking", labels)  # fallback to original order

    # Convert ranking positions to relative strengths (0.0-1.0)
    strengths: dict[str, float] = {}
    n = len(ranking)
    for pos, label in enumerate(ranking):
        if pos < len(batch):
            idx = ord(label.lower()) - ord('a')
            if 0 <= idx < len(batch):
                # Higher position = higher strength (reverse of position index)
                strengths[batch[idx]["id"]] = 1.0 - (pos / max(1, n - 1))

    # Ensure all hypotheses have a strength value
    for h in batch:
        if h["id"] not in strengths:
            strengths[h["id"]] = 0.5  # neutral fallback

    return strengths


def _pairwise_compare(
    client: anthropic.Anthropic,
    ha: Hypothesis,
    hb: Hypothesis,
    topic: str,
    criteria_block: str,
    lit_index: dict[str, str]
) -> str:
    """Compare two hypotheses and return winner ('a', 'b', or 'draw')."""
    def refs_note(h: Hypothesis) -> str:
        refs = h.get("references", [])
        titles = [lit_index[r] for r in refs if r in lit_index]
        return f" [cites: {'; '.join(titles)}]" if titles else ""

    prompt = (
        f"Topic: {topic}\n\n"
        f"Hypothesis A: {ha['text']}{refs_note(ha)}\n\n"
        f"Hypothesis B: {hb['text']}{refs_note(hb)}"
    )

    system = _SYSTEM_PAIRWISE.format(criteria=criteria_block)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    result: dict[str, str] = parse_json_response(message, "{")  # type: ignore[assignment]
    return result.get("winner", "draw")


def _swiss_tournament(
    client: anthropic.Anthropic,
    pool: list[Hypothesis],
    topic: str,
    criteria_block: str,
    lit_index: dict[str, str],
    rounds: int = None
) -> dict[str, float]:
    """Run a Swiss tournament system to efficiently rank hypotheses."""
    n = len(pool)
    if n <= 1:
        return {pool[0]["id"]: 0.5} if pool else {}

    # Use log₂(n) rounds for good convergence with fewer comparisons
    if rounds is None:
        rounds = max(3, int(math.log2(n)) + 1)

    # Initialize ratings from existing scores
    ratings: dict[str, float] = {h["id"]: 800.0 + h["score"] * 400.0 for h in pool}
    wins: dict[str, int] = {h["id"]: 0 for h in pool}

    pool_copy = pool.copy()

    for round_num in range(rounds):
        # Sort by current rating for pairing
        pool_copy.sort(key=lambda h: ratings[h["id"]], reverse=True)

        # Swiss pairing: pair adjacent players in the sorted list
        pairs = []
        paired = set()

        for i in range(0, len(pool_copy) - 1, 2):
            if pool_copy[i]["id"] not in paired and pool_copy[i + 1]["id"] not in paired:
                pairs.append((pool_copy[i], pool_copy[i + 1]))
                paired.update([pool_copy[i]["id"], pool_copy[i + 1]["id"]])

        # Process pairs in parallel
        def compare_pair(pair_data: tuple[Hypothesis, Hypothesis]) -> tuple[str, str, str]:
            ha, hb = pair_data
            winner = _pairwise_compare(client, ha, hb, topic, criteria_block, lit_index)
            return ha["id"], hb["id"], winner

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(compare_pair, pairs))

        # Update ratings based on results
        for ha_id, hb_id, winner in results:
            if winner == "a":
                wins[ha_id] += 1
            elif winner == "b":
                wins[hb_id] += 1
            # Update Elo ratings
            ratings[ha_id], ratings[hb_id] = _elo_update(ratings[ha_id], ratings[hb_id], winner)

    return ratings


def _batch_tournament(
    client: anthropic.Anthropic,
    pool: list[Hypothesis],
    topic: str,
    criteria_block: str,
    lit_index: dict[str, str]
) -> dict[str, float]:
    """Use batch comparisons to efficiently rank moderate-sized pools."""
    n = len(pool)
    if n <= 1:
        return {pool[0]["id"]: 800.0 + pool[0]["score"] * 400.0} if pool else {}

    ratings: dict[str, float] = {h["id"]: 800.0 + h["score"] * 400.0 for h in pool}

    # Process in batches
    batch_size = min(_MAX_BATCH_SIZE, max(3, n // 3))  # Adaptive batch size

    # Create overlapping batches for more comparisons
    batches = []
    for i in range(0, n, batch_size - 1):  # Overlap by 1 for continuity
        batch = pool[i:i + batch_size]
        if len(batch) >= 2:
            batches.append(batch)

    def process_batch(batch: list[Hypothesis]) -> dict[str, float]:
        return _batch_compare_hypotheses(client, batch, topic, criteria_block, lit_index)

    # Process batches in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        batch_results = list(executor.map(process_batch, batches))

    # Aggregate results: average strengths across batches where hypotheses appear
    strength_sums: dict[str, float] = {h["id"]: 0.0 for h in pool}
    strength_counts: dict[str, int] = {h["id"]: 0 for h in pool}

    for batch_strengths in batch_results:
        for hyp_id, strength in batch_strengths.items():
            strength_sums[hyp_id] += strength
            strength_counts[hyp_id] += 1

    # Convert to final ratings
    final_ratings: dict[str, float] = {}
    for hyp_id in strength_sums:
        if strength_counts[hyp_id] > 0:
            avg_strength = strength_sums[hyp_id] / strength_counts[hyp_id]
            # Scale to Elo range and mix with existing score
            base_rating = ratings[hyp_id]
            new_rating = 600.0 + avg_strength * 800.0  # 600-1400 range
            final_ratings[hyp_id] = 0.7 * new_rating + 0.3 * base_rating
        else:
            final_ratings[hyp_id] = ratings[hyp_id]

    return final_ratings


def run(state: ResearchState) -> dict[str, object]:
    """Run optimized tournament system with batching, Swiss rounds, or classic pairwise."""
    client = anthropic.Anthropic()

    pool = latest_hypotheses(state["hypotheses"])
    if not pool:
        return {
            "ranked_ids": [],
            "top_hypotheses": [],
            "messages": [{"role": "agent", "agent": "ranking", "content": "no hypotheses to rank"}],
        }

    n = len(pool)
    criteria_block = criteria_prompt_block()

    # Build literature title index for context in prompts
    lit_context: list[dict[str, str]] = state.get("literature_context") or []
    lit_index: dict[str, str] = {
        p["paper_id"]: p.get("title", "") for p in lit_context if p.get("paper_id")
    }

    # Choose ranking strategy based on pool size
    if n >= _SWISS_TOURNAMENT_THRESHOLD:
        # Large pool: Swiss tournament system
        ratings = _swiss_tournament(client, pool, state["topic"], criteria_block, lit_index)
        strategy = f"Swiss tournament ({math.ceil(math.log2(n)) + 1} rounds)"
        comparisons = len(pool) // 2 * (math.ceil(math.log2(n)) + 1)
    elif n >= _BATCH_COMPARISON_THRESHOLD:
        # Medium pool: batch comparisons
        ratings = _batch_tournament(client, pool, state["topic"], criteria_block, lit_index)
        strategy = f"batch comparisons ({_MAX_BATCH_SIZE} per batch)"
        # Estimate: overlapping batches reduce total comparisons significantly
        batches = math.ceil(n / (_MAX_BATCH_SIZE - 1))
        comparisons = batches * _MAX_BATCH_SIZE
    else:
        # Small pool: classic pairwise tournament (O(n²) but acceptable for small n)
        ratings = {h["id"]: 800.0 + h["score"] * 400.0 for h in pool}

        pairs = list(combinations(pool, 2))
        for ha, hb in pairs:
            winner = _pairwise_compare(client, ha, hb, state["topic"], criteria_block, lit_index)
            ratings[ha["id"]], ratings[hb["id"]] = _elo_update(
                ratings[ha["id"]], ratings[hb["id"]], winner
            )

        strategy = f"pairwise tournament"
        comparisons = len(pairs)

    # Normalize ratings back to 0.0–1.0 score
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
            references=h.get("references", []),
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
                    f"Ranked {n} hypotheses via {strategy} "
                    f"({comparisons} comparisons vs {n*(n-1)//2} full pairwise); "
                    f"top: {ranked_ids[:3]}"
                ),
            }
        ],
    }
