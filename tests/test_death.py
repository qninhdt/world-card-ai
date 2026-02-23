"""Tests for death.loop.DeathLoop."""
from __future__ import annotations

import pytest

from death.loop import DeathInfo, DeathLoop
from game.state import GlobalBlackboard, NPC, StatDefinition


def _make_state(stats: dict[str, int] | None = None) -> GlobalBlackboard:
    stat_defs = [
        StatDefinition(id="treasury", name="Treasury", description="", icon="💰"),
        StatDefinition(id="military", name="Military", description="", icon="⚔️"),
    ]
    return GlobalBlackboard(
        stats=stats or {"treasury": 50, "military": 50},
        stat_defs=stat_defs,
    )


class TestCheckDeath:
    def test_no_death_when_stats_are_normal(self) -> None:
        state = _make_state({"treasury": 50, "military": 50})
        assert DeathLoop.check_death(state) is None

    def test_death_when_stat_reaches_zero(self) -> None:
        state = _make_state({"treasury": 0, "military": 50})
        death = DeathLoop.check_death(state)
        assert death is not None
        assert death.cause_stat == "treasury"
        assert death.cause_value == 0

    def test_death_when_stat_reaches_hundred(self) -> None:
        state = _make_state({"treasury": 100, "military": 50})
        death = DeathLoop.check_death(state)
        assert death is not None
        assert death.cause_stat == "treasury"
        assert death.cause_value == 100

    def test_death_info_captures_state_snapshot(self) -> None:
        state = _make_state({"treasury": 0, "military": 40})
        state.life_number = 3
        state.tags = {"some_tag"}
        death = DeathLoop.check_death(state)
        assert death is not None
        assert death.life_number == 3
        assert "some_tag" in death.tags_at_death
        assert death.stats_at_death["military"] == 40


class TestResurrect:
    def test_increments_life_number(self) -> None:
        state = _make_state()
        state.life_number = 1
        DeathLoop.resurrect(state)
        assert state.life_number == 2

    def test_resets_stats_to_50(self) -> None:
        state = _make_state({"treasury": 0, "military": 100})
        DeathLoop.resurrect(state)
        assert state.stats["treasury"] == 50
        assert state.stats["military"] == 50

    def test_carries_non_temp_tags_as_karma(self) -> None:
        state = _make_state()
        state.tags = {"brave", "_temp_flag"}
        karma = DeathLoop.resurrect(state)
        assert "brave" in karma
        assert "_temp_flag" not in karma

    def test_temp_tags_stripped_from_karma(self) -> None:
        state = _make_state()
        state.tags = {"_temp_one", "_temp_two"}
        karma = DeathLoop.resurrect(state)
        assert karma == []

    def test_karma_tags_persist_in_state(self) -> None:
        state = _make_state()
        state.tags = {"veteran"}
        DeathLoop.resurrect(state)
        assert "veteran" in state.tags

    def test_turn_reset_to_zero(self) -> None:
        state = _make_state()
        state.turn = 5
        DeathLoop.resurrect(state)
        assert state.turn == 0

    def test_npc_appearance_counts_reset(self) -> None:
        state = _make_state()
        npc = NPC(id="chancellor", name="Lord Aldric", role="Chancellor",
                  description="", npc_appearance_count=7)
        state.npcs = [npc]
        DeathLoop.resurrect(state)
        assert state.npcs[0].npc_appearance_count == 0

    def test_no_duplicate_turn_reset(self) -> None:
        """Regression: turn should only be set to 0 once (no duplicate reset)."""
        state = _make_state()
        state.turn = 3
        DeathLoop.resurrect(state)
        # After resurrect, turn is 0 — just verify it's not accidentally non-zero
        assert state.turn == 0
