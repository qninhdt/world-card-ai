"""Card validator — sanitizes Writer output before insertion into the deque."""

from __future__ import annotations

import uuid
import random

from agents.schemas import FunctionCall
from cards.models import Card, Choice, ChoiceCard, InfoCard
from game.state import GlobalBlackboard


# Priority constants
PRIORITY_FILTER = 0
PRIORITY_COMMON = 1
PRIORITY_EVENT = 2
PRIORITY_PLOT = 3
PRIORITY_TREE = 4
PRIORITY_STORY = 5

SOURCE_TO_PRIORITY = {
    "common": PRIORITY_COMMON,
    "event": PRIORITY_EVENT,
    "plot": PRIORITY_PLOT,
    "tree": PRIORITY_TREE,
    "story": PRIORITY_STORY,
}


def _validate_character(npc_id: str, known_ids: set[str]) -> str:
    if npc_id in known_ids or npc_id == "narrator":
        return npc_id
    return "narrator"


def _validate_function_calls(calls: list[dict] | list[FunctionCall]) -> list[FunctionCall]:
    """Coerce raw dicts into FunctionCall models if needed."""
    result = []
    for c in calls:
        if isinstance(c, FunctionCall):
            result.append(c)
        elif isinstance(c, dict):
            result.append(FunctionCall(
                name=c.get("name", ""),
                params=c.get("params", {}),
            ))
    return result


def validate_card_def(card_def, state: GlobalBlackboard) -> Card:
    """Validate and convert a CardDef (union) into a Card (union)."""
    from agents.schemas import ChoiceCardDef, InfoCardDef

    known_ids = {n.id for n in state.npcs} | {"narrator"}
    card_id = getattr(card_def, "id", None) or uuid.uuid4().hex[:8]

    character = _validate_character(card_def.character, known_ids)
    source = card_def.source if card_def.source in SOURCE_TO_PRIORITY else "common"
    priority = SOURCE_TO_PRIORITY.get(source, PRIORITY_COMMON)

    if isinstance(card_def, InfoCardDef):
        next_cards = [validate_card_def(nc, state) for nc in getattr(card_def, 'next_cards', [])]
        return InfoCard(
            id=card_id,
            title=card_def.title,
            description=card_def.description,
            character=character,
            source=source,
            priority=priority,
            next_cards=next_cards,
        )

    # ChoiceCardDef
    left = Choice(
        text=card_def.left_text,
        calls=_validate_function_calls(getattr(card_def, 'left_calls', [])),
    )
    right = Choice(
        text=card_def.right_text,
        calls=_validate_function_calls(getattr(card_def, 'right_calls', [])),
    )

    # Recursively validate tree cards
    tree_left = [validate_card_def(nd, state) for nd in getattr(card_def, 'tree_left', [])]
    tree_right = [validate_card_def(nd, state) for nd in getattr(card_def, 'tree_right', [])]

    # Randomly swap left and right choices
    if random.choice([True, False]):
        left, right = right, left
        tree_left, tree_right = tree_right, tree_left

    return ChoiceCard(
        id=card_id,
        title=card_def.title,
        description=card_def.description,
        character=character,
        left=left,
        right=right,
        source=source,
        priority=priority,
        tree_left=tree_left,
        tree_right=tree_right,
    )
