"""Tests for cards.validator.validate_card_def."""
from __future__ import annotations

import pytest

from agents.schemas import ChoiceCardDef, FunctionCall, InfoCardDef
from cards.models import ChoiceCard, InfoCard
from cards.validator import validate_card_def
from game.state import GlobalBlackboard, NPC, StatDefinition


def _make_state() -> GlobalBlackboard:
    return GlobalBlackboard(
        stats={"treasury": 50},
        stat_defs=[StatDefinition(id="treasury", name="Treasury", description="", icon="💰")],
        npcs=[NPC(id="chancellor", name="Lord Aldric", role="", description="")],
    )


def _choice_def(npc: str = "narrator") -> ChoiceCardDef:
    return ChoiceCardDef(
        id="card_01",
        title="Test Card",
        description="A test",
        character=npc,
        left_text="Left",
        right_text="Right",
        left_calls=[],
        right_calls=[],
        source="common",
    )


class TestValidateChoiceCardDef:
    def test_returns_choice_card(self) -> None:
        state = _make_state()
        card = validate_card_def(_choice_def(), state)
        assert isinstance(card, ChoiceCard)

    def test_known_npc_character_preserved(self) -> None:
        state = _make_state()
        card = validate_card_def(_choice_def(npc="chancellor"), state)
        assert card.character == "chancellor"

    def test_unknown_npc_falls_back_to_narrator(self) -> None:
        state = _make_state()
        card = validate_card_def(_choice_def(npc="unknown_npc"), state)
        assert card.character == "narrator"

    def test_narrator_character_preserved(self) -> None:
        state = _make_state()
        card = validate_card_def(_choice_def(npc="narrator"), state)
        assert card.character == "narrator"

    def test_generates_id_when_none(self) -> None:
        state = _make_state()
        cd = _choice_def()
        cd.id = None  # type: ignore[assignment]
        card = validate_card_def(cd, state)
        assert card.id  # Should be auto-generated uuid

    def test_invalid_source_defaults_to_common(self) -> None:
        state = _make_state()
        cd = _choice_def()
        cd.source = "invalid_source"
        card = validate_card_def(cd, state)
        assert card.source == "common"


class TestValidateInfoCardDef:
    def test_returns_info_card(self) -> None:
        state = _make_state()
        cd = InfoCardDef(
            id="info_01",
            title="Info",
            description="Some info",
            character="narrator",
            source="common",
        )
        card = validate_card_def(cd, state)
        assert isinstance(card, InfoCard)

    def test_next_cards_are_validated_recursively(self) -> None:
        state = _make_state()
        nested = InfoCardDef(
            id="nested_01",
            title="Nested",
            description="Nested info",
            character="narrator",
            source="common",
        )
        cd = InfoCardDef(
            id="info_01",
            title="Info",
            description="",
            character="narrator",
            source="common",
            next_cards=[nested],
        )
        card = validate_card_def(cd, state)
        assert isinstance(card, InfoCard)
        assert len(card.next_cards) == 1
        assert isinstance(card.next_cards[0], InfoCard)
