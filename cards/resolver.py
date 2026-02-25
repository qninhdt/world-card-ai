"""Action executor — applies AI-generated function calls to the game state.

``ActionExecutor`` is the bridge between the declarative ``FunctionCall``
objects produced by the AI and the mutable ``GlobalBlackboard``.  It
implements eleven game actions:

  ``update_stat``           — change a stat value by a delta (clamped 0–100).
  ``add_tag`` / ``remove_tag`` — add or remove a string tag from the player.
  ``add_event``             — create and register a new in-game event.
  ``remove_event``          — remove an event by ID.
  ``advance_event``         — advance a PhaseEvent to its next phase.
  ``update_event_progress`` — increment a ProgressEvent's counter.
  ``change_event_deadline`` — update a TimedEvent's deadline.
  ``enable_npc``            — make an NPC available for card generation.
  ``disable_npc``           — hide an NPC from card generation.
  ``advance_time``          — fast-forward the calendar by N days.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.schemas import FunctionCall
from cards.models import Card, ChoiceCard, InfoCard
from game.events import (
    ConditionEvent,
    Event,
    EventPhase,
    PhaseEvent,
    ProgressEvent,
    TimedEvent,
)
from game.state import GlobalBlackboard


# ── Execution Result ────────────────────────────────────────────────────────


class ExecuteResult(BaseModel):
    """Result of executing function calls for an action."""

    stat_changes: dict[str, int] = {}
    new_stats: dict[str, int] = {}
    tags_added: list[str] = []
    tags_removed: list[str] = []
    tree_cards: list[Card] = []
    direction: str = "left"
    is_info: bool = False


# ── Action Executor ─────────────────────────────────────────────────────────


class ActionExecutor:
    """Executes function calls from card choices against game state."""

    def __init__(self, state: GlobalBlackboard, events: list[Event]) -> None:
        self.state = state
        self.events = events
        self._registry: dict[str, Any] = {
            "update_stat": self._update_stat,
            "add_tag": self._add_tag,
            "remove_tag": self._remove_tag,
            "add_event": self._add_event,
            "remove_event": self._remove_event,
            "advance_event": self._advance_event,
            "update_event_progress": self._update_event_progress,
            "change_event_deadline": self._change_event_deadline,
            "enable_npc": self._enable_npc,
            "disable_npc": self._disable_npc,
            "advance_time": self._advance_time,
        }

    def execute(self, calls: list[FunctionCall]) -> dict[str, int]:
        """Execute a list of function calls and return a dict of stat changes.

        Unknown function names are silently ignored so forward-compatible AI
        output does not crash older engine versions.
        """
        stat_changes: dict[str, int] = {}
        for call in calls:
            handler = self._registry.get(call.name)
            if handler:
                result = handler(call.params)
                if call.name == "update_stat" and result:
                    stat_changes.update(result)
        return stat_changes

    def resolve_card(self, card: Card, direction: str) -> ExecuteResult:
        """Resolve a card action and return an ``ExecuteResult``.

        For ``ChoiceCard``: executes the chosen side's function calls and
        tracks the NPC appearance counter.
        For ``InfoCard``: no calls are executed; ``next_cards`` are returned
        as tree cards so they appear immediately after dismissal.
        """
        # Note: day advancement is handled by GameEngine.resolve_card, not here.

        if isinstance(card, InfoCard):
            return ExecuteResult(
                direction=direction,
                is_info=True,
                tree_cards=list(card.next_cards),
            )

        # ChoiceCard
        choice = card.left if direction == "left" else card.right
        stat_changes = self.execute(choice.calls)

        # Track NPC appearance
        npc = next((n for n in self.state.npcs if n.id == card.character), None)
        if npc:
            npc.npc_appearance_count += 1

        tree_cards = card.tree_left if direction == "left" else card.tree_right

        return ExecuteResult(
            stat_changes=stat_changes,
            new_stats=dict(self.state.stats),
            tags_added=[],  # tracked during execute
            tags_removed=[],
            tree_cards=tree_cards,
            direction=direction,
            is_info=False,
        )

    # ── Function Implementations ────────────────────────────────────────

    def _update_stat(self, params: dict) -> dict[str, int]:
        """Apply a delta to one or more stats, clamping each value to [0, 100].

        Supports two calling conventions from the AI:
          1. ``{stat_id: "x", delta: 5}`` — explicit stat + delta pair.
          2. ``{treasury: 5, military: -3}`` — dict of stat_id → delta pairs.
        """
        changes = {}
        # Support {stat_id: str, delta|change: int} format
        if "stat_id" in params and ("delta" in params or "change" in params):
            stat_id = params["stat_id"]
            delta = params.get("delta", params.get("change", 0))
            try:
                delta = int(delta)
            except (TypeError, ValueError):
                return changes
            if stat_id in self.state.stats:
                old = self.state.stats[stat_id]
                new = max(0, min(100, old + delta))
                self.state.stats[stat_id] = new
                changes[stat_id] = new - old
        else:
            # Dict format: {"treasury": 5, "military": -3}
            for stat_id, delta in params.items():
                try:
                    delta = int(delta)
                except (TypeError, ValueError):
                    continue
                if stat_id in self.state.stats:
                    old = self.state.stats[stat_id]
                    new = max(0, min(100, old + delta))
                    self.state.stats[stat_id] = new
                    changes[stat_id] = new - old
        return changes

    def _add_tag(self, params: dict) -> None:
        tag_id = params.get("tag_id", "")
        if tag_id:
            self.state.tags.add(tag_id)

    def _remove_tag(self, params: dict) -> None:
        tag_id = params.get("tag_id", "")
        self.state.tags.discard(tag_id)

    def _add_event(self, params: dict) -> None:
        event_type = params.get("type", "phase")
        event_id = params.get("event_id", "")
        if not event_id:
            return

        base_kwargs = {
            "id": event_id,
            "name": params.get("name", event_id.replace("_", " ").title()),
            "description": params.get("description", ""),
            "icon": params.get("icon", "⚡"),
        }

        if event_type == "phase":
            phases = [
                EventPhase(name=p.get("name", ""), description=p.get("description", ""))
                for p in params.get("phases", [])
            ]
            event = PhaseEvent(**base_kwargs, phases=phases)
        elif event_type == "progress":
            event = ProgressEvent(
                **base_kwargs,
                target=params.get("target", 0),
                progress_label=params.get("progress_label", ""),
            )
        elif event_type == "timed":
            event = TimedEvent(
                **base_kwargs,
                deadline=params.get("deadline", [1, 1, 1]),
            )
        elif event_type == "condition":
            event = ConditionEvent(
                **base_kwargs,
                end_condition=params.get("end_condition", ""),
            )
        else:
            return

        self.events.append(event)

    def _remove_event(self, params: dict) -> None:
        event_id = params.get("event_id", "")
        self.events[:] = [e for e in self.events if e.id != event_id]

    def _advance_event(self, params: dict) -> None:
        event_id = params.get("event_id", "")
        for event in self.events:
            if event.id == event_id and isinstance(event, PhaseEvent):
                event.advance_phase()
                break

    def _update_event_progress(self, params: dict) -> None:
        event_id = params.get("event_id", "")
        delta = params.get("delta", 0)
        for event in self.events:
            if event.id == event_id and isinstance(event, ProgressEvent):
                event.update_progress(delta)
                break

    def _change_event_deadline(self, params: dict) -> None:
        event_id = params.get("event_id", "")
        deadline = params.get("deadline", [])
        for event in self.events:
            if event.id == event_id and isinstance(event, TimedEvent):
                event.set_deadline(deadline)
                break

    def _enable_npc(self, params: dict) -> None:
        npc_id = params.get("npc_id", "")
        for npc in self.state.npcs:
            if npc.id == npc_id:
                npc.enabled = True
                break

    def _disable_npc(self, params: dict) -> None:
        npc_id = params.get("npc_id", "")
        for npc in self.state.npcs:
            if npc.id == npc_id:
                npc.enabled = False
                break

    def _advance_time(self, params: dict) -> None:
        days = params.get("days", 0)
        if days > 0:
            for _ in range(days):
                self.state.advance_day()
