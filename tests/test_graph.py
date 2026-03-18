"""Tests for graph construction."""


def test_build_graph_returns_compiled() -> None:
    from darwin.graph import build_graph

    graph = build_graph()
    assert graph is not None
