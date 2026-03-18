"""ResearchState and Hypothesis TypedDicts for the AI Co-Scientist graph."""
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


class ResearchState(TypedDict):
    # --- Core inputs (set once by CLI / human) ---
    topic: str                              # Research question / domain
    max_iterations: int                     # Hard stop for the loop

    # --- Iteration tracking ---
    iteration: int                          # Current loop counter (starts at 0)

    # --- Hypothesis pool ---
    hypotheses: Annotated[list[Hypothesis], operator.add]
    # operator.add reducer: agents append new hypotheses; never overwrite the list

    # --- Per-iteration working state ---
    ranked_ids: list[str]                   # Ordered hypothesis ids from ranking agent
    top_hypotheses: list[Hypothesis]        # Top-N after ranking (passed to evolution)
    proximity_clusters: list[list[str]]     # Groups of similar hypothesis ids

    # --- Supervisor / meta state ---
    supervisor_decision: str                # "continue" | "stop" | "human_review"
    meta_review_notes: str                  # Cumulative meta-review observations
    human_feedback: str | None             # Text entered by human during review pause
    final_hypotheses: list[Hypothesis]      # Written at loop exit

    # --- Plumbing ---
    messages: Annotated[list[dict], operator.add]
    # Full message log for tracing (each agent appends its output message)
