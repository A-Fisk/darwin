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
| **Ranking** | Runs an Elo pairwise tournament; literature-grounded hypotheses get a boost |
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
6. **Ranking** runs an Elo tournament; literature-backed hypotheses gain an advantage when otherwise equal.
7. **Proximity** clusters the top pool by semantic theme.
8. **Meta-review** audits progress across iterations and issues a decision:
   - `continue` — keep iterating
   - `stop` — hypotheses are good enough
   - `human_review` — pause and ask the user
9. If `human_review` is triggered, the terminal displays the current top hypotheses and prompts for feedback. Type `stop` to halt, or enter any text to guide the next iteration.
10. When the loop ends, the final ranked hypotheses and meta-review notes are printed.

---

## Configuring evaluation criteria

Evaluation criteria are defined in `src/darwin/criteria.toml`. Edit the file to tune what the system values without touching agent code:

```toml
[[criteria]]
name = "novelty"
description = "The hypothesis proposes something genuinely new..."
weight = 1.0

[[criteria]]
name = "literature_support"
description = "The hypothesis builds on or extends the retrieved literature..."
weight = 0.8
```

Each criterion has a `name`, `description` (shown to the LLM judge), and `weight` (relative importance; normalised at runtime).

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
