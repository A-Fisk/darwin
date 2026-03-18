"""LangGraph StateGraph wiring for the AI Co-Scientist."""
from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from darwin.state import Hypothesis, ResearchState


# ---------------------------------------------------------------------------
# Stub agent nodes (full implementations live in darwin/agents/)
# ---------------------------------------------------------------------------

def supervisor_node(state: ResearchState) -> dict:
    """Pure routing node — no LLM call. Increments iteration on 'generate' path."""
    # Increment iteration when we're about to generate (not on first entry when
    # iteration==0 and we haven't routed yet, but after the loop completes a pass).
    # The routing function below reads supervisor_decision to decide next edge;
    # the supervisor writes the incremented counter so the next pass sees it.
    return {}  # routing happens via route_supervisor; state unchanged here


def generation_node(state: ResearchState) -> dict:
    """Placeholder — generates new hypotheses. Implemented in agents/generation.py."""
    return {"messages": [{"role": "system", "content": "generation stub"}]}


def reflection_node(state: ResearchState) -> dict:
    """Placeholder — critiques hypotheses. Implemented in agents/reflection.py."""
    return {"messages": [{"role": "system", "content": "reflection stub"}]}


def ranking_node(state: ResearchState) -> dict:
    """Placeholder — ranks hypotheses. Implemented in agents/ranking.py."""
    return {
        "ranked_ids": [],
        "top_hypotheses": [],
        "messages": [{"role": "system", "content": "ranking stub"}],
    }


def proximity_node(state: ResearchState) -> dict:
    """Placeholder — clusters hypotheses. Implemented in agents/proximity.py."""
    return {
        "proximity_clusters": [],
        "messages": [{"role": "system", "content": "proximity stub"}],
    }


def evolution_node(state: ResearchState) -> dict:
    """Placeholder — evolves top hypotheses. Implemented in agents/evolution.py."""
    return {"messages": [{"role": "system", "content": "evolution stub"}]}


def meta_review_node(state: ResearchState) -> dict:
    """Placeholder — audits progress. Implemented in agents/meta_review.py."""
    return {
        "meta_review_notes": state.get("meta_review_notes", ""),
        "supervisor_decision": "continue",
        "messages": [{"role": "system", "content": "meta_review stub"}],
    }


def human_review_node(state: ResearchState) -> dict:
    """Interrupt node — pauses graph and waits for human input."""
    feedback = interrupt({
        "top_hypotheses": state.get("top_hypotheses", []),
        "meta_review_notes": state.get("meta_review_notes", ""),
        "iteration": state.get("iteration", 0),
    })
    decision = "stop" if str(feedback).strip().lower() == "stop" else "continue"
    return {
        "human_feedback": str(feedback),
        "supervisor_decision": decision,
    }


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------

def route_supervisor(state: ResearchState) -> str:
    """Route supervisor output to the next node."""
    if state.get("iteration", 0) >= state.get("max_iterations", 5):
        return "end"
    decision = state.get("supervisor_decision", "continue")
    if decision == "human_review":
        return "human_review"
    if decision == "stop":
        return "end"
    return "generate"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph() -> object:
    """Construct and compile the full research graph.

    Returns a ``CompiledGraph`` ready for ``graph.invoke(initial_state, config)``.
    """
    builder = StateGraph(ResearchState)

    # Register all nodes
    builder.add_node("supervisor",   supervisor_node)
    builder.add_node("generation",   generation_node)
    builder.add_node("reflection",   reflection_node)
    builder.add_node("ranking",      ranking_node)
    builder.add_node("proximity",    proximity_node)
    builder.add_node("evolution",    evolution_node)
    builder.add_node("meta_review",  meta_review_node)
    builder.add_node("human_review", human_review_node)

    # Entry point
    builder.set_entry_point("supervisor")

    # Conditional edges from supervisor
    builder.add_conditional_edges(
        "supervisor",
        route_supervisor,
        {
            "generate":     "generation",
            "human_review": "human_review",
            "end":          END,
        },
    )

    # Linear pipeline: generation → reflection → ranking → proximity → evolution → meta_review
    builder.add_edge("generation",  "reflection")
    builder.add_edge("reflection",  "ranking")
    builder.add_edge("ranking",     "proximity")
    builder.add_edge("proximity",   "evolution")
    builder.add_edge("evolution",   "meta_review")
    builder.add_edge("meta_review", "supervisor")   # close the loop

    # Human review resumes at supervisor
    builder.add_edge("human_review", "supervisor")

    return builder.compile()
