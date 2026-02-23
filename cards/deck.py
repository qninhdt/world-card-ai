"""Priority-weighted card deck used by the game engine.

``WeightedDeque`` stores cards sorted by priority so the highest-priority card
is always drawn first (O(n) insert via bisect, O(1) draw from the tail).

Priority levels (defined in ``cards.validator``):
  5 = story  (death / reborn / welcome)
  4 = tree   (branching follow-up cards)
  3 = plot   (DAG narrative cards)
  2 = event  (active-event cards)
  1 = common (normal AI-generated cards)
  0 = filter (suppressed cards — never drawn)

When the deck exceeds ``capacity`` the lowest-priority *common* card is evicted
so that plot/event/tree/story cards are never lost.
"""

from __future__ import annotations

import bisect

from cards.models import Card, CardBase, ChoiceCard, InfoCard


class WeightedDeque:
    """A priority deque that draws highest-priority cards first.

    Uses card.priority (0-5) for ordering:
      5=story, 4=tree, 3=plot, 2=event, 1=common, 0=filter

    Eviction policy: when over capacity, evict the lowest-priority common cards.
    Non-common cards (plot, event, tree, story) are never evicted.
    """

    def __init__(self, capacity: int = 10) -> None:
        self._cards: list[Card] = []
        self.capacity = capacity
        self.cards_consumed: int = 0

    def draw(self) -> Card | None:
        """Remove and return the highest-priority card, or None if empty."""
        if not self._cards:
            return None
        card = self._cards.pop()
        self.cards_consumed += 1
        return card

    def insert(self, card: Card) -> None:
        """Insert a single card in priority order using bisect."""
        priorities = [c.priority for c in self._cards]
        idx = bisect.bisect_left(priorities, card.priority)
        self._cards.insert(idx, card)
        self._evict_if_needed()

    def bulk_insert(self, cards: list[Card]) -> int:
        """Insert multiple cards in priority order and evict if necessary.

        Returns the number of cards inserted (before eviction).
        """
        for card in cards:
            priorities = [c.priority for c in self._cards]
            idx = bisect.bisect_left(priorities, card.priority)
            self._cards.insert(idx, card)
        self._evict_if_needed()
        return len(cards)

    def _evict_if_needed(self) -> None:
        while len(self._cards) > self.capacity:
            evicted = False
            for i, card in enumerate(self._cards):
                if card.source == "common":
                    self._cards.pop(i)
                    evicted = True
                    break
            if not evicted:
                break

    def clear(self) -> None:
        self._cards.clear()
        self.cards_consumed = 0

    @property
    def count(self) -> int:
        return len(self._cards)

    @property
    def needs_generation(self) -> bool:
        threshold = max(1, self.capacity // 2)
        return self.cards_consumed >= threshold

    def reset_consumption_counter(self) -> None:
        self.cards_consumed = 0

    @property
    def is_empty(self) -> bool:
        return len(self._cards) == 0

    @property
    def status(self) -> str:
        return f"{len(self._cards)}/{self.capacity}"

    def peek_all(self) -> list[Card]:
        """Return a copy of all cards, highest priority first (does not mutate the deck)."""
        return list(reversed(self._cards))
