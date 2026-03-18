"""ResearchState TypedDict and related types."""
from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class Hypothesis(TypedDict):
    id: str                      # uuid4 short hex
    text: str                    # The hypothesis statement
    score: float                 # Aggregate ranking score (0.0–1.0)
    reflections: list[str]       # Critique notes from reflection agent
    generation: int              # Which iteration produced this hypothesis
    evolved_from: str | None     # Parent hypothesis id, or None
    references: list[str]        # Paper IDs from literature_context that support this hypothesis


class ResearchState(TypedDict):
    # --- Core inputs (set once by CLI / human) ---
    topic: str
    max_iterations: int

    # --- Iteration tracking ---
    iteration: int

    # --- Hypothesis pool ---
    hypotheses: Annotated[list[Hypothesis], operator.add]

    # --- Literature context (fetched once per run by literature agent) ---
    literature_context: list[dict[str, str]]  # fields: title, abstract, authors, url, paper_id

    # --- Per-iteration working state ---
    ranked_ids: list[str]
    top_hypotheses: list[Hypothesis]
    proximity_clusters: list[list[str]]

    # --- Supervisor / meta state ---
    supervisor_decision: str        # "continue" | "stop" | "human_review"
    meta_review_notes: str
    human_feedback: str | None
    final_hypotheses: list[Hypothesis]

    # --- Plumbing ---
    messages: Annotated[list[dict[str, object]], operator.add]
