"""Card data models — the core unit of interaction in the game.

There are two card types:

``ChoiceCard`` — presented with a left and right swipe option.  Each option
carries a list of ``FunctionCall`` objects that the ``ActionExecutor`` applies
to the game state.  Choices may also carry *tree cards* that are queued
immediately after the current card is resolved.

``InfoCard`` — read-only narrative card.  The player dismisses it with either
swipe direction without triggering any stat changes.  ``next_cards`` allows
chaining multiple info cards together.

The ``Card`` union type (discriminated by the ``type`` field) is used
throughout the codebase so mypy can narrow the concrete type safely.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from agents.schemas import FunctionCall


# ── Choice ──────────────────────────────────────────────────────────────────


class Choice(BaseModel):
    text: str
    calls: list[FunctionCall] = Field(default_factory=list)


# ── Card Base ───────────────────────────────────────────────────────────────


class CardBase(BaseModel):
    id: str
    title: str
    description: str
    character: str
    source: str = "common"  # common | plot | event | tree
    priority: int = 1  # 0=filter, 1=common, 2=event, 3=plot, 4=tree, 5=story


# ── Choice Card ─────────────────────────────────────────────────────────────


class ChoiceCard(CardBase):
    """Card with left/right swipe choices."""

    type: Literal["choice"] = "choice"
    left: Choice
    right: Choice
    tree_left: list[Card] = []
    tree_right: list[Card] = []


# ── Info Card ───────────────────────────────────────────────────────────────


class InfoCard(CardBase):
    """Read-only card. Player dismisses to continue.

    next_cards allows splitting long info messages across multiple cards.
    When dismissed, the next card in the chain is shown immediately.
    """

    type: Literal["info"] = "info"
    next_cards: list[Card] = []


# ── Union Type ──────────────────────────────────────────────────────────────

Card = Annotated[Union[ChoiceCard, InfoCard], Field(discriminator="type")]

# Rebuild for forward references
ChoiceCard.model_rebuild()
InfoCard.model_rebuild()
