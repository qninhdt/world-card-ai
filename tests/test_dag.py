"""Tests for story.dag.MacroDAG."""
from __future__ import annotations

import pytest

from agents.schemas import FunctionCall
from game.state import GlobalBlackboard, Season, StatDefinition
from story.dag import MacroDAG, PlotNode


def _make_state(stats: dict[str, int] | None = None, tags: set[str] | None = None) -> GlobalBlackboard:
    return GlobalBlackboard(
        stats=stats or {"treasury": 50, "military": 50},
        stat_defs=[
            StatDefinition(id="treasury", name="Treasury", description="", icon="💰"),
            StatDefinition(id="military", name="Military", description="", icon="⚔️"),
        ],
        tags=tags or set(),
        seasons=[Season(name="Spring", description="", icon="🌸")],
    )


def _node(node_id: str, condition: str = "True", is_ending: bool = False) -> PlotNode:
    return PlotNode(
        id=node_id,
        plot_description=f"Description of {node_id}",
        condition=condition,
        is_ending=is_ending,
    )


class TestAddNodeAndEdge:
    def test_add_node(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("n1"))
        assert "n1" in dag.nodes

    def test_add_edge_creates_directed_link(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("n1"))
        dag.add_node(_node("n2"))
        dag.add_edge("n1", "n2")
        assert ("n1", "n2") in dag.graph.edges()

    def test_add_edge_ignores_unknown_nodes(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("n1"))
        dag.add_edge("n1", "ghost")  # ghost does not exist
        assert dag.graph.number_of_edges() == 0


class TestCheckCondition:
    def test_simple_true_condition(self) -> None:
        dag = MacroDAG()
        node = _node("n1", condition="True")
        state = _make_state()
        assert dag.check_condition(node, state) is True

    def test_simple_false_condition(self) -> None:
        dag = MacroDAG()
        node = _node("n1", condition="False")
        state = _make_state()
        assert dag.check_condition(node, state) is False

    def test_stat_based_condition(self) -> None:
        dag = MacroDAG()
        node = _node("n1", condition="stats['treasury'] > 40")
        state = _make_state(stats={"treasury": 50})
        assert dag.check_condition(node, state) is True

    def test_stat_based_condition_false(self) -> None:
        dag = MacroDAG()
        node = _node("n1", condition="stats['treasury'] > 60")
        state = _make_state(stats={"treasury": 50})
        assert dag.check_condition(node, state) is False

    def test_tag_based_condition(self) -> None:
        dag = MacroDAG()
        node = _node("n1", condition="'hero' in tags")
        state = _make_state(tags={"hero"})
        assert dag.check_condition(node, state) is True

    def test_malformed_condition_returns_false(self) -> None:
        dag = MacroDAG()
        node = _node("n1", condition="this is not valid python !!!")
        state = _make_state()
        assert dag.check_condition(node, state) is False


class TestGetActivatableNodes:
    def test_root_node_is_activatable_when_condition_met(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("root", condition="True"))
        state = _make_state()
        result = dag.get_activatable_nodes(state)
        assert any(n.id == "root" for n in result)

    def test_child_not_activatable_before_parent_fired(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("parent", condition="True"))
        dag.add_node(_node("child", condition="True"))
        dag.add_edge("parent", "child")
        state = _make_state()
        result = dag.get_activatable_nodes(state)
        ids = [n.id for n in result]
        assert "child" not in ids

    def test_child_activatable_after_parent_fired(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("parent", condition="True"))
        dag.add_node(_node("child", condition="True"))
        dag.add_edge("parent", "child")
        dag.fire_node("parent")
        state = _make_state()
        result = dag.get_activatable_nodes(state)
        ids = [n.id for n in result]
        assert "child" in ids

    def test_fired_node_not_returned_again(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("n1", condition="True"))
        dag.fire_node("n1")
        state = _make_state()
        result = dag.get_activatable_nodes(state)
        assert not any(n.id == "n1" for n in result)


class TestFireNode:
    def test_fire_node_marks_as_fired(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("n1"))
        dag.fire_node("n1")
        assert dag.nodes["n1"].is_fired is True

    def test_fire_nonexistent_node_returns_none(self) -> None:
        dag = MacroDAG()
        result = dag.fire_node("ghost")
        assert result is None


class TestCheckEnding:
    def test_ending_detected_after_fire(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("end", condition="True", is_ending=True))
        dag.fire_node("end")
        state = _make_state()
        result = dag.check_ending(state)
        assert result is not None
        assert result.id == "end"

    def test_no_ending_before_fire(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("end", condition="True", is_ending=True))
        state = _make_state()
        assert dag.check_ending(state) is None


class TestPartialReset:
    def test_resets_non_ending_nodes(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("n1"))
        dag.fire_node("n1")
        dag.partial_reset()
        assert dag.nodes["n1"].is_fired is False

    def test_keeps_ending_nodes_fired(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("end", is_ending=True))
        dag.fire_node("end")
        dag.partial_reset(keep_fired={"end"})
        assert dag.nodes["end"].is_fired is True


class TestValidateReachability:
    def test_no_warnings_for_simple_chain(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("a"))
        dag.add_node(_node("b"))
        dag.add_edge("a", "b")
        warnings = dag.validate_reachability()
        assert warnings == []

    def test_warning_for_node_with_only_ending_predecessor(self) -> None:
        dag = MacroDAG()
        dag.add_node(_node("end", is_ending=True))
        dag.add_node(_node("orphan"))
        dag.add_edge("end", "orphan")
        warnings = dag.validate_reachability()
        assert any("orphan" in w for w in warnings)
