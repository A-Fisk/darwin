"""Tests for ResearchState and Hypothesis TypedDicts."""
from darwin.state import Hypothesis, ResearchState


def test_hypothesis_structure() -> None:
    h: Hypothesis = {
        "id": "abc123",
        "text": "Test hypothesis",
        "score": 0.8,
        "reflections": ["good point"],
        "generation": 1,
        "evolved_from": None,
        "references": ["paper123"],
    }
    assert h["id"] == "abc123"
    assert h["evolved_from"] is None
    assert h["references"] == ["paper123"]


def test_research_state_structure() -> None:
    state: ResearchState = {
        "topic": "test topic",
        "max_iterations": 5,
        "iteration": 0,
        "hypotheses": [],
        "literature_context": [],
        "ranked_ids": [],
        "top_hypotheses": [],
        "proximity_clusters": [],
        "supervisor_decision": "continue",
        "meta_review_notes": "",
        "human_feedback": None,
        "final_hypotheses": [],
        "messages": [],
    }
    assert state["topic"] == "test topic"
    assert state["iteration"] == 0
    assert state["literature_context"] == []
