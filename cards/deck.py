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
        if not self._cards:
            return None
        card = self._cards.pop()
        self.cards_consumed += 1
        return card

    def insert(self, card: Card) -> None:
        priorities = [c.priority for c in self._cards]
        idx = bisect.bisect_left(priorities, card.priority)
        self._cards.insert(idx, card)
        self._evict_if_needed()

    def bulk_insert(self, cards: list[Card]) -> int:
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
        return list(reversed(self._cards))
