"""Tests for game.engine.GameEngine core logic."""
from __future__ import annotations

import pytest

from agents.schemas import FunctionCall
from cards.models import Choice, ChoiceCard, InfoCard
from game.demo import get_demo_world
from game.engine import GameEngine


def _make_engine() -> GameEngine:
    """Return an engine initialised with the demo world."""
    engine = GameEngine()
    world = get_demo_world()
    engine.build_from_schema(world, stat_count=4)
    return engine


def _simple_choice_card(card_id: str = "c1") -> ChoiceCard:
    return ChoiceCard(
        id=card_id,
        title="Test",
        description="",
        character="narrator",
        source="common",
        priority=1,
        left=Choice(text="left", calls=[]),
        right=Choice(text="right", calls=[]),
    )


class TestBuildFromSchema:
    def test_stats_initialised_to_50(self) -> None:
        engine = _make_engine()
        for value in engine.state.stats.values():
            assert value == 50

    def test_npcs_loaded(self) -> None:
        engine = _make_engine()
        assert len(engine.state.npcs) > 0

    def test_dag_nodes_built(self) -> None:
        engine = _make_engine()
        assert len(engine.dag.nodes) > 0

    def test_seasons_loaded(self) -> None:
        engine = _make_engine()
        assert len(engine.state.seasons) == 4


class TestDrawCard:
    def test_draw_from_empty_returns_none(self) -> None:
        engine = _make_engine()
        assert engine.draw_card() is None

    def test_draw_from_immediate_deque_first(self) -> None:
        engine = _make_engine()
        info = InfoCard(id="urgent", title="Urgent", description="", character="narrator")
        engine.immediate_deque.append(info)
        engine.deque.insert(_simple_choice_card())
        drawn = engine.draw_card()
        assert drawn is not None
        assert drawn.id == "urgent"

    def test_draw_from_deck_when_immediate_empty(self) -> None:
        engine = _make_engine()
        engine.deque.insert(_simple_choice_card("deck_card"))
        drawn = engine.draw_card()
        assert drawn is not None
        assert drawn.id == "deck_card"


class TestResolveCard:
    def test_advances_day(self) -> None:
        engine = _make_engine()
        card = _simple_choice_card()
        initial_day = engine.state.day
        engine.resolve_card(card, "left")
        assert engine.state.day == initial_day + 1

    def test_info_card_does_not_advance_day(self) -> None:
        engine = _make_engine()
        card = InfoCard(id="i1", title="", description="", character="narrator")
        initial_day = engine.state.day
        engine.resolve_card(card, "left")
        assert engine.state.day == initial_day


class TestCheckDeath:
    def test_no_death_at_start(self) -> None:
        engine = _make_engine()
        assert engine.check_death() is None

    def test_death_detected_when_stat_zero(self) -> None:
        engine = _make_engine()
        first_stat = next(iter(engine.state.stats))
        engine.state.stats[first_stat] = 0
        assert engine.check_death() is not None


class TestIsWeekOver:
    def test_week_not_over_with_cards(self) -> None:
        engine = _make_engine()
        engine.deque.insert(_simple_choice_card())
        assert engine.is_week_over is False

    def test_week_over_when_both_queues_empty(self) -> None:
        engine = _make_engine()
        assert engine.is_week_over is True


class TestGetCommonCount:
    def test_full_count_when_no_jobs(self) -> None:
        engine = _make_engine()
        assert engine.get_common_count() == engine.get_week_deck_size()

    def test_reduced_by_pending_jobs(self) -> None:
        from game.job_queue import CardGenJob
        engine = _make_engine()
        engine.job_queue.enqueue(CardGenJob(job_type="plot", context={}))
        engine.job_queue.enqueue(CardGenJob(job_type="plot", context={}))
        count = engine.get_common_count()
        assert count == max(1, engine.get_week_deck_size() - 2)


class TestPrepareDemoWeek:
    def test_fills_deck_with_cards(self) -> None:
        engine = _make_engine()
        engine.prepare_demo_week()
        assert engine.deque.count > 0

    def test_welcome_card_queued_on_first_day_life_1(self) -> None:
        engine = _make_engine()
        # Set start_day = 0 so elapsed_days = 1 (day=1, start_day=0, same season/year)
        engine.state.start_day = 0
        engine.state.life_number = 1
        engine.state.day = 1
        assert engine.state.elapsed_days == 1
        engine.prepare_demo_week()
        ids = [c.id for c in engine.immediate_deque]
        assert any("welcome" in cid or "season" in cid for cid in ids)

    def test_death_cards_created_for_all_stats_on_day_1(self) -> None:
        engine = _make_engine()
        engine.state.day = 1
        engine.prepare_demo_week()
        # 4 stats × 2 boundaries = 8 death card entries
        assert len(engine.state.pending_death_cards) == 8


class TestHandleDeath:
    def test_death_card_added_to_immediate_deque(self) -> None:
        engine = _make_engine()
        first_stat = next(iter(engine.state.stats))
        engine.state.stats[first_stat] = 0
        death = engine.check_death()
        assert death is not None
        engine.handle_death(death)
        assert len(engine.immediate_deque) == 1
        assert engine._awaiting_resurrection is True

    def test_complete_resurrection_resets_flag(self) -> None:
        engine = _make_engine()
        first_stat = next(iter(engine.state.stats))
        engine.state.stats[first_stat] = 0
        death = engine.check_death()
        assert death is not None
        engine.handle_death(death)
        engine.complete_resurrection()
        assert engine._awaiting_resurrection is False


class TestCheckEvents:
    def test_removes_finished_phase_event(self) -> None:
        from game.events import PhaseEvent
        engine = _make_engine()
        event = PhaseEvent(id="evt", name="E", description="", phases=[])
        # No phases → is_finished is True from the start
        engine.events = [event]
        engine.check_events()
        assert len(engine.events) == 0

    def test_keeps_active_progress_event(self) -> None:
        from game.events import ProgressEvent
        engine = _make_engine()
        event = ProgressEvent(id="quest", name="Q", description="", target=5)
        engine.events = [event]
        engine.check_events()
        assert len(engine.events) == 1
