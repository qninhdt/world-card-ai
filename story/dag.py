from __future__ import annotations

import logging
import networkx as nx
from pydantic import BaseModel, Field

from agents.schemas import FunctionCall
from game.state import GlobalBlackboard

logger = logging.getLogger(__name__)


class PlotNode(BaseModel):
    """Description-only plot node. The Writer generates the actual card."""

    id: str
    plot_description: str
    condition: str = "True"  # Python expression evaluated via eval()
    calls: list[FunctionCall] = []  # functions to run when this node fires
    is_ending: bool = False
    ending_text: str | None = None
    is_fired: bool = False


class MacroDAG:
    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self.nodes: dict[str, PlotNode] = {}

    def add_node(self, node: PlotNode) -> None:
        self.nodes[node.id] = node
        self.graph.add_node(node.id)

    def add_edge(self, from_id: str, to_id: str) -> None:
        if from_id in self.nodes and to_id in self.nodes:
            self.graph.add_edge(from_id, to_id)

    def check_condition(self, node: PlotNode, state: GlobalBlackboard) -> bool:
        """Evaluate a node's condition using the state context."""
        ctx = {
            "stats": state.stats,
            "tags": state.tags,
            "events": set(),  # filled by engine with active event ids
            "season": state.season_index,
            "day": state.day,
            "year": state.year,
            "elapsed_days": state.elapsed_days,
        }
        try:
            return bool(eval(node.condition, {"__builtins__": {}}, ctx))
        except Exception:
            logger.debug("Failed to evaluate condition for node '%s': %s", node.id, node.condition, exc_info=True)
            return False

    def get_activatable_nodes(self, state: GlobalBlackboard) -> list[PlotNode]:
        """Get nodes whose predecessors are all fired and conditions are met."""
        result = []
        for node_id, node in self.nodes.items():
            if node.is_fired:
                continue
            preds = list(self.graph.predecessors(node_id))
            if preds and not all(self.nodes[p].is_fired for p in preds if p in self.nodes):
                continue
            if self.check_condition(node, state):
                result.append(node)
        return result

    def fire_node(self, node_id: str) -> PlotNode | None:
        """Mark a node as fired and return it."""
        node = self.nodes.get(node_id)
        if not node:
            return None
        node.is_fired = True
        return node

    def check_ending(self, state: GlobalBlackboard) -> PlotNode | None:
        for node in self.nodes.values():
            if node.is_ending and node.is_fired:
                return node
        return None

    def partial_reset(self, keep_fired: set[str] | None = None) -> None:
        for node_id, node in self.nodes.items():
            if keep_fired and node_id in keep_fired:
                continue
            if not node.is_ending:
                node.is_fired = False

    def validate_reachability(self) -> list[str]:
        """Check that all non-root nodes have at least one satisfiable path."""
        warnings = []
        for node_id, node in self.nodes.items():
            preds = list(self.graph.predecessors(node_id))
            if not preds:
                continue
            reachable_preds = [p for p in preds if p in self.nodes]
            if not reachable_preds:
                warnings.append(f"Node '{node_id}' has no reachable predecessors")
            if all(self.nodes[p].is_ending for p in reachable_preds):
                warnings.append(f"Node '{node_id}' only has ending predecessors — unreachable")
        return warnings

    def get_writer_context(self, state: GlobalBlackboard) -> dict:
        """Pruned DAG context for the Writer."""
        fired = []
        activatable = []
        activatable_ids = set()

        for node_id, node in self.nodes.items():
            if node.is_fired:
                fired.append({"id": node_id, "description": node.plot_description[:80]})
            else:
                preds = list(self.graph.predecessors(node_id))
                if not preds or all(
                    self.nodes[p].is_fired for p in preds if p in self.nodes
                ):
                    activatable_ids.add(node_id)
                    activatable.append({
                        "id": node_id,
                        "description": node.plot_description,
                        "is_ending": node.is_ending,
                        "condition": node.condition,
                    })

        upcoming = []
        for aid in activatable_ids:
            for child_id in self.graph.successors(aid):
                child = self.nodes.get(child_id)
                if child and not child.is_fired and child_id not in activatable_ids:
                    upcoming.append({
                        "id": child_id,
                        "condition": child.condition,
                    })

        return {"fired": fired, "activatable": activatable, "upcoming": upcoming}

    def get_visual_graph(self) -> dict:
        """Export full DAG structure for UI visualization."""
        nodes_info = {}
        for node_id, node in self.nodes.items():
            preds = list(self.graph.predecessors(node_id))
            succs = list(self.graph.successors(node_id))

            if node.is_fired:
                status = "fired"
            elif not preds or all(
                self.nodes[p].is_fired for p in preds if p in self.nodes
            ):
                status = "activatable"
            else:
                status = "locked"

            nodes_info[node_id] = {
                "description": node.plot_description,
                "status": status,
                "is_ending": node.is_ending,
                "ending_text": node.ending_text,
                "condition": node.condition,
                "predecessors": preds,
                "successors": succs,
            }

        return {
            "nodes": nodes_info,
            "edges": list(self.graph.edges()),
        }
