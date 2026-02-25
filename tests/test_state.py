"""Tests for game.state.GlobalBlackboard."""
from __future__ import annotations

import pytest

from game.state import (
    DAYS_PER_SEASON,
    DAYS_PER_WEEK,
    SEASONS_PER_YEAR,
    GlobalBlackboard,
    Season,
    StatDefinition,
)


def _make_seasons() -> list[Season]:
    return [
        Season(name="Spring", description="", icon="🌸"),
        Season(name="Summer", description="", icon="☀️"),
        Season(name="Autumn", description="", icon="🍂"),
        Season(name="Winter", description="", icon="❄️"),
    ]


def _make_state(stats: dict[str, int] | None = None) -> GlobalBlackboard:
    stat_defs = [
        StatDefinition(id="treasury", name="Treasury", description="", icon="💰"),
        StatDefinition(id="military", name="Military", description="", icon="⚔️"),
    ]
    return GlobalBlackboard(
        stats=stats or {"treasury": 50, "military": 50},
        stat_defs=stat_defs,
        seasons=_make_seasons(),
        start_day=1,
        start_season_index=0,
        start_year=1,
    )


class TestAdvanceDay:
    def test_no_boundary_crossed(self) -> None:
        state = _make_state()
        crossed = state.advance_day()
        assert state.day == 2
        assert crossed["week_end"] is False
        assert crossed["season_end"] is False

    def test_week_end_crossed(self) -> None:
        state = _make_state()
        # Advance 6 more turns to hit turn == DAYS_PER_WEEK (7)
        for _ in range(DAYS_PER_WEEK - 1):
            state.advance_day()
        crossed = state.advance_day()
        assert crossed["week_end"] is True
        assert state.turn == 0

    def test_season_end_crossed(self) -> None:
        state = _make_state()
        state.day = DAYS_PER_SEASON  # last day of season
        crossed = state.advance_day()
        assert crossed["season_end"] is True
        assert state.day == 1
        assert state.season_index == 1

    def test_year_wraps_when_all_seasons_pass(self) -> None:
        state = _make_state()
        state.day = DAYS_PER_SEASON
        state.season_index = SEASONS_PER_YEAR - 1
        state.advance_day()
        assert state.season_index == 0
        assert state.year == 2


class TestElapsedDays:
    def test_zero_at_start(self) -> None:
        state = _make_state()
        assert state.elapsed_days == 0

    def test_increments_with_advance_day(self) -> None:
        state = _make_state()
        state.advance_day()
        assert state.elapsed_days == 1


class TestCurrentSeason:
    def test_returns_correct_season(self) -> None:
        state = _make_state()
        season = state.current_season()
        assert season is not None
        assert season.name == "Spring"

    def test_returns_none_when_no_seasons(self) -> None:
        state = GlobalBlackboard()
        assert state.current_season() is None


class TestWeekInSeason:
    def test_first_day_is_week_1(self) -> None:
        state = _make_state()
        assert state.week_in_season == 1

    def test_day_8_is_week_2(self) -> None:
        state = _make_state()
        state.day = DAYS_PER_WEEK + 1
        assert state.week_in_season == 2


class TestGetStatHelpers:
    def test_get_stat_name_known(self) -> None:
        state = _make_state()
        assert state.get_stat_name("treasury") == "Treasury"

    def test_get_stat_name_unknown_returns_id(self) -> None:
        state = _make_state()
        assert state.get_stat_name("nonexistent") == "nonexistent"

    def test_get_stat_icon_known(self) -> None:
        state = _make_state()
        assert state.get_stat_icon("treasury") == "💰"

    def test_get_stat_icon_unknown_returns_question_mark(self) -> None:
        state = _make_state()
        assert state.get_stat_icon("nonexistent") == "?"
