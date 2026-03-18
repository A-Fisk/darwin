# AI Co-Scientist — Design: State, Graph, Agent Contracts

> Reference document for `da-tdo`. Consumed by implementers of `da-t2q` (state.py / graph.py) and `da-7nx` (agent nodes).

---

## 1. ResearchState TypedDict

```python
from __future__ import annotations
from typing import TypedDict, Annotated
import operator

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
```

### Reducer notes

- `hypotheses` and `messages` use `operator.add` so concurrent node writes merge correctly.
- All other fields use last-write-wins (LangGraph default).
- `ranked_ids`, `top_hypotheses`, and `proximity_clusters` are reset each iteration by their respective agents.

---

## 2. Graph Topology

```
                      ┌──────────┐
         topic ──────►│supervisor│◄──── human_feedback (after review)
                      └────┬─────┘
                           │ route()
            ┌──────────────┼───────────────┐
            ▼              ▼               ▼
      [generation]   [human_review]    [END / stop]
            │
            ▼
      [reflection]
            │
            ▼
        [ranking]
            │
            ▼
       [proximity]
            │
            ▼
       [evolution]
            │
            ▼
      [meta_review]
            │
            └──────────────► supervisor  (loop back)
```

### LangGraph node list

| Node name      | Type            | Description |
|----------------|-----------------|-------------|
| `supervisor`   | conditional hub | Routes each iteration to generation, human_review, or END |
| `generation`   | agent node      | Generates new hypotheses |
| `reflection`   | agent node      | Critiques and scores each hypothesis |
| `ranking`      | agent node      | Sorts hypotheses; populates `ranked_ids` / `top_hypotheses` |
| `proximity`    | agent node      | Clusters hypotheses by semantic similarity |
| `evolution`    | agent node      | Mutates / combines top hypotheses into new candidates |
| `meta_review`  | agent node      | Cross-iteration quality audit; updates `meta_review_notes` |
| `human_review` | interrupt node  | Pauses graph; resumes with `human_feedback` |

### Edge wiring (pseudo-code)

```python
graph.add_node("supervisor",   supervisor_node)
graph.add_node("generation",   generation_node)
graph.add_node("reflection",   reflection_node)
graph.add_node("ranking",      ranking_node)
graph.add_node("proximity",    proximity_node)
graph.add_node("evolution",    evolution_node)
graph.add_node("meta_review",  meta_review_node)
graph.add_node("human_review", human_review_node)

graph.set_entry_point("supervisor")

graph.add_conditional_edges("supervisor", route_supervisor, {
    "generate":      "generation",
    "human_review":  "human_review",
    "end":           END,
})

graph.add_edge("generation",  "reflection")
graph.add_edge("reflection",  "ranking")
graph.add_edge("ranking",     "proximity")
graph.add_edge("proximity",   "evolution")
graph.add_edge("evolution",   "meta_review")
graph.add_edge("meta_review", "supervisor")   # closes the loop

graph.add_edge("human_review", "supervisor")  # resume after human input
```

---

## 3. Agent Contracts

Each section specifies: **Reads** (state fields consumed), **Writes** (state fields produced), **LLM prompt intent**, and **Tool use** (if any).

---

### 3.1 supervisor

**Purpose:** Decide what happens next each iteration.

| | Fields |
|---|---|
| Reads | `iteration`, `max_iterations`, `supervisor_decision`, `meta_review_notes`, `human_feedback`, `ranked_ids` |
| Writes | `supervisor_decision`, `iteration` (increments) |

**Routing logic (`route_supervisor`):**

```python
def route_supervisor(state: ResearchState) -> str:
    if state["iteration"] >= state["max_iterations"]:
        return "end"
    if state["supervisor_decision"] == "human_review":
        return "human_review"
    return "generate"
```

**No LLM call.** Pure deterministic routing based on iteration counter and previous `supervisor_decision`. `meta_review_notes` may trigger `human_review` if the meta agent signals low quality.

---

### 3.2 generation

**Purpose:** Brainstorm fresh hypotheses for the research topic.

| | Fields |
|---|---|
| Reads | `topic`, `iteration`, `meta_review_notes`, `proximity_clusters` |
| Writes | `hypotheses` (appends N new `Hypothesis` objects) |

**Prompt intent:**
> "Given topic `{topic}` and prior observations `{meta_review_notes}`, generate `{N}` novel, testable research hypotheses. Avoid ideas similar to cluster centroids `{proximity_clusters}`."

**Output:** List of `Hypothesis` dicts with `score=0.0`, `reflections=[]`, `evolved_from=None`.

---

### 3.3 reflection

**Purpose:** Critique each hypothesis for quality, novelty, and feasibility.

| | Fields |
|---|---|
| Reads | `hypotheses` (current iteration's new ones) |
| Writes | `hypotheses` (updates `reflections` and initial `score` on each new hypothesis) |

**Prompt intent:**
> "For each hypothesis, provide a brief critique and a quality score 0–1 covering: scientific plausibility, novelty, testability."

**Implementation note:** Reflection iterates over hypotheses added this iteration only (filter by `generation == state["iteration"]`).

---

### 3.4 ranking

**Purpose:** Produce a total ordering of all hypotheses by score.

| | Fields |
|---|---|
| Reads | `hypotheses` |
| Writes | `ranked_ids`, `top_hypotheses` |

**Prompt intent:**
> "Given the following hypotheses with scores and reflections, produce a ranked list from best to worst. Top `{TOP_N}` form the elite set."

`top_hypotheses` = top-N `Hypothesis` objects (N configurable, default 3).

**May use deterministic sort** on `score` rather than LLM, with LLM as optional tiebreaker.

---

### 3.5 proximity

**Purpose:** Identify clusters of semantically similar hypotheses to guide diversity.

| | Fields |
|---|---|
| Reads | `hypotheses`, `top_hypotheses` |
| Writes | `proximity_clusters` |

**Prompt intent:**
> "Group the following hypothesis texts into clusters of highly similar ideas. Return each cluster as a list of hypothesis ids."

**Implementation options:** LLM clustering via prompt, or embedding + k-means. Contract is identical either way.

---

### 3.6 evolution

**Purpose:** Produce improved hypotheses by mutating or combining top candidates.

| | Fields |
|---|---|
| Reads | `top_hypotheses`, `meta_review_notes`, `iteration` |
| Writes | `hypotheses` (appends evolved `Hypothesis` objects with `evolved_from` set) |

**Prompt intent:**
> "Given these top hypotheses, produce `{N}` evolved variants by: (a) refining the weakest element of a single hypothesis, or (b) synthesizing two hypotheses into a stronger combined claim."

Each evolved hypothesis sets `evolved_from = parent.id`.

---

### 3.7 meta_review

**Purpose:** Audit overall progress across iterations; suggest adjustments.

| | Fields |
|---|---|
| Reads | `hypotheses`, `ranked_ids`, `iteration`, `meta_review_notes` |
| Writes | `meta_review_notes`, `supervisor_decision` |

**Prompt intent:**
> "Review progress across `{iteration}` iterations. Are hypotheses converging without novelty? Is quality improving? Provide updated notes and recommend: continue, stop, or human_review."

**Key output:** Sets `supervisor_decision` to one of `"continue"` / `"stop"` / `"human_review"`. The supervisor reads this on the next iteration.

---

### 3.8 human_review (interrupt node)

**Purpose:** Pause execution and surface top hypotheses to the human operator.

| | Fields |
|---|---|
| Reads | `top_hypotheses`, `iteration`, `meta_review_notes` |
| Writes | `human_feedback`, `supervisor_decision` |

**Behavior:**

1. Display ranked hypotheses and meta notes via rich CLI output.
2. Prompt user: `"Enter feedback or 'continue' / 'stop':"`.
3. Write response to `human_feedback`.
4. If user says `"stop"`, set `supervisor_decision = "stop"`.
5. Otherwise set `supervisor_decision = "continue"` and resume.

**LangGraph interrupt pattern:**

```python
from langgraph.types import interrupt

def human_review_node(state: ResearchState) -> dict:
    # Display state to CLI here (rich output)
    feedback = interrupt({
        "top_hypotheses": state["top_hypotheses"],
        "meta_review_notes": state["meta_review_notes"],
        "iteration": state["iteration"],
    })
    decision = "stop" if str(feedback).strip().lower() == "stop" else "continue"
    return {
        "human_feedback": str(feedback),
        "supervisor_decision": decision,
    }
```

The graph is resumed by calling `graph.invoke(Command(resume=user_input), config)`.

---

## 4. Iteration Loop

```
iteration 0
  supervisor → route="generate"
  generation → reflection → ranking → proximity → evolution → meta_review
  meta_review sets supervisor_decision = "continue" | "human_review" | "stop"
  → supervisor (iteration 1)

iteration N (when supervisor_decision == "human_review")
  supervisor → route="human_review"
  human_review: interrupt → human types feedback → resume
  → supervisor (iteration N+1, decision reset to "continue")

iteration M (when iteration >= max_iterations OR decision == "stop")
  supervisor → route="end"
  graph copies top_hypotheses → final_hypotheses
  → END
```

### Loop invariants

- `iteration` is incremented by supervisor at the **start** of each loop pass (after routing "generate").
- `hypotheses` is append-only; old hypotheses are never deleted.
- `ranked_ids` and `top_hypotheses` are **replaced** each iteration by ranking.
- `proximity_clusters` is **replaced** each iteration by proximity.

---

## 5. Configuration Constants (to live in `config.py`)

| Constant | Default | Used by |
|---|---|---|
| `TOP_N_HYPOTHESES` | 3 | ranking, evolution |
| `NEW_PER_ITERATION` | 5 | generation |
| `EVOLVED_PER_ITERATION` | 3 | evolution |
| `DEFAULT_MAX_ITERATIONS` | 5 | CLI / supervisor |
| `HUMAN_REVIEW_INTERVAL` | None (disabled unless meta_review triggers) | meta_review |

---

## 6. Files This Design Implies

```
darwin/
  src/
    darwin/
      state.py        # ResearchState + Hypothesis TypedDicts
      graph.py        # build_graph() → CompiledGraph
      agents/
        __init__.py
        supervisor.py
        generation.py
        reflection.py
        ranking.py
        proximity.py
        evolution.py
        meta_review.py
        human_review.py
      config.py       # Constants above
      cli.py          # Entry point, rich output
  tests/
    test_state.py
    test_graph.py
    test_agents/
  pyproject.toml
```
