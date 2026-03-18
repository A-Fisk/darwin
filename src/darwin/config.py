"""Configuration constants for darwin agents."""

TOP_N_HYPOTHESES: int = 3
NEW_PER_ITERATION: int = 5
EVOLVED_PER_ITERATION: int = 3
DEFAULT_MAX_ITERATIONS: int = 5
HUMAN_REVIEW_INTERVAL: int | None = None  # None = disabled unless meta_review triggers
