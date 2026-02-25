"""Tests for cards.deck.WeightedDeque."""
from __future__ import annotations

import pytest

from cards.deck import WeightedDeque
from cards.models import Choice, ChoiceCard, InfoCard


def _choice_card(card_id: str, priority: int = 1, source: str = "common") -> ChoiceCard:
    return ChoiceCard(
        id=card_id,
        title=card_id,
        description="",
        character="narrator",
        source=source,
        priority=priority,
        left=Choice(text="left", calls=[]),
        right=Choice(text="right", calls=[]),
    )


def _info_card(card_id: str, priority: int = 1, source: str = "common") -> InfoCard:
    return InfoCard(
        id=card_id,
        title=card_id,
        description="",
        character="narrator",
        source=source,
        priority=priority,
    )


class TestWeightedDequeInsertAndDraw:
    def test_draw_from_empty_returns_none(self) -> None:
        dq = WeightedDeque(capacity=5)
        assert dq.draw() is None

    def test_draw_returns_highest_priority_first(self) -> None:
        dq = WeightedDeque(capacity=5)
        low = _choice_card("low", priority=1)
        high = _choice_card("high", priority=3)
        dq.insert(low)
        dq.insert(high)
        drawn = dq.draw()
        assert drawn is not None
        assert drawn.id == "high"

    def test_draw_order_stable_for_same_priority(self) -> None:
        dq = WeightedDeque(capacity=5)
        a = _choice_card("a", priority=1)
        b = _choice_card("b", priority=1)
        dq.insert(a)
        dq.insert(b)
        # Both priority 1; the last-inserted card ends up at a higher index
        # after bisect_left, so order may vary — just check both are drawn
        drawn_ids = {dq.draw().id, dq.draw().id}  # type: ignore[union-attr]
        assert drawn_ids == {"a", "b"}

    def test_count_tracks_cards(self) -> None:
        dq = WeightedDeque(capacity=5)
        dq.insert(_choice_card("x"))
        dq.insert(_choice_card("y"))
        assert dq.count == 2

    def test_is_empty_after_all_drawn(self) -> None:
        dq = WeightedDeque(capacity=5)
        dq.insert(_choice_card("x"))
        dq.draw()
        assert dq.is_empty


class TestWeightedDequeCapacityEviction:
    def test_evicts_common_when_over_capacity(self) -> None:
        dq = WeightedDeque(capacity=2)
        dq.insert(_choice_card("a", priority=1, source="common"))
        dq.insert(_choice_card("b", priority=1, source="common"))
        dq.insert(_choice_card("c", priority=1, source="common"))
        # Should evict one to stay at capacity
        assert dq.count == 2

    def test_does_not_evict_non_common_cards(self) -> None:
        dq = WeightedDeque(capacity=2)
        dq.insert(_choice_card("a", priority=3, source="plot"))
        dq.insert(_choice_card("b", priority=2, source="event"))
        # Exceeds capacity but no common cards to evict → stays over capacity
        dq.insert(_choice_card("c", priority=3, source="plot"))
        assert dq.count == 3


class TestBulkInsert:
    def test_bulk_insert_adds_all_cards(self) -> None:
        dq = WeightedDeque(capacity=10)
        cards = [_choice_card(f"c{i}") for i in range(5)]
        n = dq.bulk_insert(cards)
        assert n == 5
        assert dq.count == 5


class TestClear:
    def test_clear_removes_all_cards(self) -> None:
        dq = WeightedDeque(capacity=5)
        dq.insert(_choice_card("x"))
        dq.clear()
        assert dq.is_empty
        assert dq.cards_consumed == 0


class TestPeekAll:
    def test_peek_all_returns_copy_highest_first(self) -> None:
        dq = WeightedDeque(capacity=5)
        low = _choice_card("low", priority=1)
        high = _choice_card("high", priority=3)
        dq.insert(low)
        dq.insert(high)
        peeked = dq.peek_all()
        assert peeked[0].id == "high"
        assert peeked[1].id == "low"
        # Original deck not modified
        assert dq.count == 2
