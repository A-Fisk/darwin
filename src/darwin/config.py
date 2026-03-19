"""Configuration constants for darwin agents."""

TOP_N_HYPOTHESES: int = 3
NEW_PER_ITERATION: int = 5
EVOLVED_PER_ITERATION: int = 3
DEFAULT_MAX_ITERATIONS: int = 5
HUMAN_REVIEW_INTERVAL: int | None = None  # None = disabled unless meta_review triggers

# Token limits for LLM calls - tiered by task complexity
MAX_TOKENS_SIMPLE: int = 256      # Simple decisions, short responses
MAX_TOKENS_STANDARD: int = 512    # Standard responses, brief analysis
MAX_TOKENS_DETAILED: int = 1024   # Detailed comparisons, critiques
MAX_TOKENS_COMPLEX: int = 2048    # Complex analysis, rankings
MAX_TOKENS_CREATIVE: int = 4096   # Hypothesis generation, evolution
