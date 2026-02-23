"""Tests for cards.resolver.ActionExecutor."""
from __future__ import annotations

import pytest

from agents.schemas import FunctionCall
from cards.models import Choice, ChoiceCard, InfoCard
from cards.resolver import ActionExecutor, ExecuteResult
from game.events import PhaseEvent, EventPhase, ProgressEvent, TimedEvent, ConditionEvent
from game.state import GlobalBlackboard, NPC, StatDefinition


def _make_state(stats: dict[str, int] | None = None) -> GlobalBlackboard:
    return GlobalBlackboard(
        stats=stats or {"treasury": 50, "military": 50},
        stat_defs=[
            StatDefinition(id="treasury", name="Treasury", description="", icon="💰"),
            StatDefinition(id="military", name="Military", description="", icon="⚔️"),
        ],
    )


def _fc(name: str, **params) -> FunctionCall:
    return FunctionCall(name=name, params=params)


def _choice(calls: list[FunctionCall]) -> Choice:
    return Choice(text="ok", calls=calls)


def _choice_card(left_calls: list[FunctionCall], right_calls: list[FunctionCall]) -> ChoiceCard:
    return ChoiceCard(
        id="test_card",
        title="Test",
        description="",
        character="narrator",
        left=_choice(left_calls),
        right=_choice(right_calls),
    )


class TestUpdateStat:
    def test_delta_format(self) -> None:
        state = _make_state()
        executor = ActionExecutor(state, [])
        executor.execute([_fc("update_stat", stat_id="treasury", delta=10)])
        assert state.stats["treasury"] == 60

    def test_change_alias(self) -> None:
        state = _make_state()
        executor = ActionExecutor(state, [])
        executor.execute([_fc("update_stat", stat_id="treasury", change=-5)])
        assert state.stats["treasury"] == 45

    def test_dict_format(self) -> None:
        state = _make_state()
        executor = ActionExecutor(state, [])
        executor.execute([FunctionCall(name="update_stat", params={"treasury": 20})])
        assert state.stats["treasury"] == 70

    def test_stat_clamps_at_100(self) -> None:
        state = _make_state({"treasury": 95})
        executor = ActionExecutor(state, [])
        executor.execute([_fc("update_stat", stat_id="treasury", delta=20)])
        assert state.stats["treasury"] == 100

    def test_stat_clamps_at_0(self) -> None:
        state = _make_state({"treasury": 5})
        executor = ActionExecutor(state, [])
        executor.execute([_fc("update_stat", stat_id="treasury", delta=-20)])
        assert state.stats["treasury"] == 0

    def test_unknown_stat_ignored(self) -> None:
        state = _make_state()
        executor = ActionExecutor(state, [])
        executor.execute([_fc("update_stat", stat_id="ghost", delta=10)])
        # No error, state unchanged
        assert "ghost" not in state.stats


class TestTagActions:
    def test_add_tag(self) -> None:
        state = _make_state()
        executor = ActionExecutor(state, [])
        executor.execute([_fc("add_tag", tag_id="hero")])
        assert "hero" in state.tags

    def test_remove_tag(self) -> None:
        state = _make_state()
        state.tags = {"hero"}
        executor = ActionExecutor(state, [])
        executor.execute([_fc("remove_tag", tag_id="hero")])
        assert "hero" not in state.tags

    def test_remove_nonexistent_tag_is_safe(self) -> None:
        state = _make_state()
        executor = ActionExecutor(state, [])
        executor.execute([_fc("remove_tag", tag_id="ghost")])  # should not raise


class TestNPCActions:
    def _state_with_npc(self) -> GlobalBlackboard:
        state = _make_state()
        state.npcs = [NPC(id="guard", name="Guard", role="", description="", enabled=True)]
        return state

    def test_disable_npc(self) -> None:
        state = self._state_with_npc()
        executor = ActionExecutor(state, [])
        executor.execute([_fc("disable_npc", npc_id="guard")])
        assert state.npcs[0].enabled is False

    def test_enable_npc(self) -> None:
        state = self._state_with_npc()
        state.npcs[0].enabled = False
        executor = ActionExecutor(state, [])
        executor.execute([_fc("enable_npc", npc_id="guard")])
        assert state.npcs[0].enabled is True


class TestAddEvent:
    def test_add_phase_event(self) -> None:
        state = _make_state()
        events: list = []
        executor = ActionExecutor(state, events)
        executor.execute([FunctionCall(name="add_event", params={
            "type": "phase",
            "event_id": "war",
            "name": "War",
            "description": "A war",
            "icon": "⚔️",
            "phases": [{"name": "Phase1", "description": "First phase"}],
        })])
        assert len(events) == 1
        assert isinstance(events[0], PhaseEvent)

    def test_add_progress_event(self) -> None:
        state = _make_state()
        events: list = []
        executor = ActionExecutor(state, events)
        executor.execute([FunctionCall(name="add_event", params={
            "type": "progress",
            "event_id": "quest",
            "name": "Quest",
            "description": "A quest",
            "target": 5,
            "progress_label": "steps",
        })])
        assert isinstance(events[0], ProgressEvent)
        assert events[0].target == 5

    def test_add_event_without_id_is_ignored(self) -> None:
        state = _make_state()
        events: list = []
        executor = ActionExecutor(state, events)
        executor.execute([FunctionCall(name="add_event", params={"type": "phase"})])
        assert len(events) == 0


class TestRemoveEvent:
    def test_remove_event_by_id(self) -> None:
        state = _make_state()
        events: list = [PhaseEvent(id="war", name="War", description="", phases=[])]
        executor = ActionExecutor(state, events)
        executor.execute([_fc("remove_event", event_id="war")])
        assert len(events) == 0


class TestResolveCard:
    def test_resolve_choice_card_left(self) -> None:
        state = _make_state()
        card = _choice_card(
            left_calls=[_fc("update_stat", stat_id="treasury", delta=10)],
            right_calls=[_fc("update_stat", stat_id="treasury", delta=-10)],
        )
        executor = ActionExecutor(state, [])
        result = executor.resolve_card(card, "left")
        assert result.direction == "left"
        assert state.stats["treasury"] == 60

    def test_resolve_choice_card_right(self) -> None:
        state = _make_state()
        card = _choice_card(
            left_calls=[],
            right_calls=[_fc("update_stat", stat_id="military", delta=5)],
        )
        executor = ActionExecutor(state, [])
        result = executor.resolve_card(card, "right")
        assert state.stats["military"] == 55

    def test_resolve_info_card_returns_is_info(self) -> None:
        state = _make_state()
        card = InfoCard(
            id="info1", title="Info", description="", character="narrator"
        )
        executor = ActionExecutor(state, [])
        result = executor.resolve_card(card, "left")
        assert result.is_info is True

    def test_resolve_choice_card_increments_npc_appearances(self) -> None:
        state = _make_state()
        npc = NPC(id="chancellor", name="Lord", role="", description="")
        state.npcs = [npc]
        card = _choice_card([], [])
        card.character = "chancellor"
        executor = ActionExecutor(state, [])
        executor.resolve_card(card, "left")
        assert state.npcs[0].npc_appearance_count == 1
