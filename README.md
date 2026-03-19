# darwin

**AI Co-Scientist** — a multi-agent research hypothesis system inspired by Google's AI Co-Scientist.

Given a research question, darwin runs a self-improving loop of specialized agents that generate, critique, rank, cluster, and evolve scientific hypotheses until they converge on high-quality candidates.

Built with [LangGraph](https://github.com/langchain-ai/langgraph) + [Claude](https://www.anthropic.com/claude).

---

## What it does

darwin orchestrates a graph of nine agents that iterate over a hypothesis pool:

| Agent | Role |
|---|---|
| **Supervisor** | Routes each iteration: continue generating, request human review, or stop |
| **Literature** | Fetches relevant papers from Semantic Scholar to ground hypothesis generation |
| **Generation** | Produces 5 new hypotheses per iteration, citing supporting papers |
| **Reflection** | Critiques each hypothesis using configurable criteria and assigns a score (0–1) |
| **Ranking** | Runs an optimized Elo tournament system; literature-grounded hypotheses get a boost |
| **Proximity** | Clusters hypotheses by semantic similarity to surface thematic groups |
| **Evolution** | Mutates and combines top hypotheses into refined candidates |
| **Meta-review** | Cross-iteration quality audit; decides whether to continue, stop, or escalate to human |
| **Human review** | Pauses the graph for interactive human feedback (triggered by meta-review) |

Each iteration runs the full pipeline (literature → generation → reflection → ranking → proximity → evolution → meta-review) and feeds results back to the supervisor.

---

## Install

Requires Python 3.11+ and [uv](https://github.com/astral-sh/uv).

```bash
# Clone and enter the repo
git clone <repo-url>
cd darwin

# Install (creates a venv automatically)
uv sync
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Run

```bash
uv run darwin "<research question>"
```

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--iterations N` | `5` | Maximum number of research iterations |
| `--output-dir DIR` | _(none)_ | Write `hypotheses.tex` and `references.bib` to DIR on completion |

**Customization**: To modify ranking criteria or algorithm settings, see the [Ranking Algorithm](#ranking-algorithm) section below.

**Examples:**

```bash
# Basic usage
uv run darwin "What causes antibiotic resistance to spread in hospital settings?"

# Run more iterations for deeper exploration
uv run darwin "Novel mechanisms for carbon capture" --iterations 10

# Save results as LaTeX + BibTeX files
uv run darwin "Novel mechanisms for carbon capture" --output-dir ./results
```

---

## How it works

1. The **supervisor** starts the first iteration.
2. **Literature** fetches up to 10 papers from [Semantic Scholar](https://www.semanticscholar.org/) for the research topic (once per run; no API key required).
3. **Generation** produces 5 new hypotheses grounded in the retrieved papers; each cites which papers it builds on.
4. **Evolution** adds 3 more hypotheses by mutating top candidates from the prior round.
5. **Reflection** critiques every new hypothesis against configurable criteria (see `criteria.toml`) and scores it (0–1).
6. **Ranking** runs an optimized tournament system with literature preference (see [Ranking Algorithm](#ranking-algorithm) below).
7. **Proximity** clusters the top pool by semantic theme.
8. **Meta-review** audits progress across iterations and issues a decision:
   - `continue` — keep iterating
   - `stop` — hypotheses are good enough
   - `human_review` — pause and ask the user
9. If `human_review` is triggered, the terminal displays the current top hypotheses and prompts for feedback. Type `stop` to halt, or enter any text to guide the next iteration.
10. When the loop ends, the final ranked hypotheses and meta-review notes are printed.

---

## Configuring evaluation criteria

Evaluation criteria are defined in `src/darwin/criteria.toml`. Edit this file to tune what the system values without touching agent code.

**Current criteria** (used by both **Reflection** and **Ranking** agents):

```toml
[[criteria]]
name = "novelty"
description = "The hypothesis proposes something genuinely new, not merely restating known results."
weight = 1.0

[[criteria]]
name = "testability"
description = "The hypothesis can be empirically tested or falsified with concrete experiments."
weight = 1.0

[[criteria]]
name = "specificity"
description = "The hypothesis is precise and makes clear, unambiguous predictions."
weight = 1.0

[[criteria]]
name = "scientific_merit"
description = "The hypothesis is scientifically plausible, internally consistent, and grounded in domain knowledge."
weight = 1.0

[[criteria]]
name = "literature_support"
description = "The hypothesis builds on, extends, challenges, or synthesises from the retrieved literature in a meaningful way."
weight = 0.8
```

Each criterion has a `name`, `description` (shown to the LLM judge), and `weight` (relative importance; normalized at runtime). Higher weights increase a criterion's influence on the final scores.

---

## Ranking Algorithm

The **Ranking** agent uses an optimized Elo tournament system to produce a total ordering of hypotheses. The algorithm adapts its strategy based on the number of hypotheses to balance accuracy and efficiency.

### How Rankings Are Determined

1. **Evaluation Criteria**: Each hypothesis is judged using the criteria defined in `criteria.toml`:
   - **novelty** (weight 1.0): Proposes something genuinely new vs. restating known results
   - **testability** (weight 1.0): Can be empirically tested or falsified with concrete experiments
   - **specificity** (weight 1.0): Makes precise, unambiguous predictions
   - **scientific_merit** (weight 1.0): Scientifically plausible, internally consistent, grounded in domain knowledge
   - **literature_support** (weight 0.8): Builds on, extends, or synthesizes from retrieved literature

2. **Literature Preference**: When all other criteria are equal, hypotheses that cite and meaningfully extend the retrieved literature receive preference over those that don't.

3. **Elo Tournament System**: Uses K=32 Elo rating updates where:
   - Winners gain rating points, losers lose them
   - The amount depends on the rating difference (upset victories gain more points)
   - Final ratings are normalized to 0.0–1.0 scores

### Adaptive Ranking Strategies

The system automatically chooses the most efficient ranking approach based on pool size:

| Pool Size | Strategy | Comparisons | Details |
|-----------|----------|-------------|---------|
| **Small (< 15)** | Pairwise Tournament | O(n²) | Direct comparison of every hypothesis pair |
| **Medium (15–24)** | Batch Comparisons | ~n×4 | Groups of 4 hypotheses ranked together |
| **Large (≥ 25)** | Swiss Tournament | ~n×log₂(n) | Smart pairing across log₂(n) rounds |

**Example**: For 8 hypotheses, the system runs 28 pairwise comparisons. For 30 hypotheses, it runs ~5 Swiss tournament rounds with smart opponent pairing.

### Top Selection

After ranking, the system selects the top N hypotheses (default: 3) to feed into the **Evolution** agent for the next iteration. This creates a selective pressure that improves hypothesis quality over time.

### Customization Options

**Evaluation Criteria** (modify `src/darwin/criteria.toml`):
```toml
[[criteria]]
name = "your_criterion"
description = "What you want to evaluate..."
weight = 1.2  # Adjust relative importance
```

**Pool Size** (modify `src/darwin/config.py`):
```python
TOP_N_HYPOTHESES: int = 5  # Default: 3
```

**Advanced Configuration** (modify thresholds in `src/darwin/agents/ranking.py`):
```python
_BATCH_COMPARISON_THRESHOLD = 15    # When to switch from pairwise
_SWISS_TOURNAMENT_THRESHOLD = 25    # When to switch to Swiss system
_MAX_BATCH_SIZE = 4                 # Hypotheses per batch comparison
```

### Example Ranking Output

```
Ranked 12 hypotheses via batch comparisons (16 comparisons vs 66 full pairwise)
Top hypotheses:
1. (score: 0.91) Horizontal gene transfer via conjugative plasmids...
2. (score: 0.87) Biofilm formation on medical devices creates...
3. (score: 0.83) Sub-therapeutic antibiotic concentrations in ICUs...
```

---

## Example output

```
Darwin Co-Scientist
Topic: What mechanisms drive antibiotic resistance in hospital settings?
Max iterations: 5

[iteration 1] generating...
[iteration 1] reflecting...
...

Final Hypotheses
────────────────
1. (score: 0.91) Horizontal gene transfer via conjugative plasmids is the
   primary driver of multi-drug resistance spread in ICU environments,
   amplified by sub-therapeutic antibiotic concentrations.

2. (score: 0.87) Biofilm formation on medical devices creates protected
   niches where resistance mutations accumulate and are periodically
   released into the patient population.

3. (score: 0.83) ...

Meta-review: Research converged after 4 iterations. Top hypotheses are
specific, testable, and cover complementary mechanisms.
```

---

## Development

```bash
# Run tests
uv run pytest

# Type-check
uv run mypy src/

# Lint
uv run ruff check src/ tests/
```
