"""LangGraph graph builder for the darwin co-scientist."""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from darwin.state import ResearchState


def build_graph(checkpointer: Any = None) -> Any:
    """Build and compile the research hypothesis graph.

    Args:
        checkpointer: Optional LangGraph checkpointer (e.g. MemorySaver) required
            for resuming after human-review interrupts.
    """
    from darwin.agents import (
        evolution,
        generation,
        human_review,
        literature,
        meta_review,
        proximity,
        ranking,
        reflection,
        supervisor,
    )

    builder: StateGraph[ResearchState] = StateGraph(ResearchState)

    builder.add_node("supervisor", supervisor.run)
    builder.add_node("literature", literature.run)
    builder.add_node("generation", generation.run)
    builder.add_node("reflection", reflection.run)
    builder.add_node("ranking", ranking.run)
    builder.add_node("proximity", proximity.run)
    builder.add_node("evolution", evolution.run)
    builder.add_node("meta_review", meta_review.run)
    builder.add_node("human_review", human_review.run)

    builder.set_entry_point("supervisor")

    builder.add_conditional_edges(
        "supervisor",
        supervisor.route,
        {
            "generate": "literature",
            "human_review": "human_review",
            "end": END,
        },
    )

    builder.add_edge("literature", "generation")
    builder.add_edge("generation", "reflection")
    builder.add_edge("reflection", "ranking")
    builder.add_edge("ranking", "proximity")
    builder.add_edge("proximity", "evolution")
    builder.add_edge("evolution", "meta_review")
    builder.add_edge("meta_review", "supervisor")
    builder.add_edge("human_review", "supervisor")

    return builder.compile(checkpointer=checkpointer)
