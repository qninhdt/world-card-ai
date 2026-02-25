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
