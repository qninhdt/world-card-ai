import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from game.engine import GameEngine
from game.state import GlobalBlackboard, StatDefinition
from agents.schemas import (
    WorldGenSchema, PlayerCharacterDef, SeasonDef, TagDef, RelationshipDef,
    NPCDef, WriterBatchOutput, ChoiceCardDef, InfoCardDef, FunctionCall, StatDef
)
from cards.models import ChoiceCard, InfoCard, Choice
import agents.writer  # Explicit import to help patch find the module

@pytest.fixture
def mock_world_schema():
    return WorldGenSchema(
        world_name="Test World",
        world_description="A test world.",
        era="Test Era",
        starting_year=1000,
        resurrection_mechanic="Reborn",
        resurrection_flavor="You rise again.",
        player_character=PlayerCharacterDef(
            id="player", name="Hero", role="Hero", description="A hero.", traits=[]
        ),
        stats=[
            StatDef(id="wealth", name="Wealth", description="Money", icon="💰"),
            StatDef(id="health", name="Health", description="HP", icon="❤"),
        ],
        npcs=[
            NPCDef(id="king", name="King", role="Ruler", description="The King", traits=[], enabled=True)
        ],
        relationships=[],
        tags=[],
        plot_nodes=[],
        seasons=[
            SeasonDef(name="Spring", description="Spring time", icon="🌸"),
            SeasonDef(name="Summer", description="Summer time", icon="☀"),
            SeasonDef(name="Autumn", description="Autumn time", icon="🍂"),
            SeasonDef(name="Winter", description="Winter time", icon="❄"),
        ]
    )

@pytest.fixture
def engine(mock_world_schema):
    eng = GameEngine()
    eng.build_from_schema(mock_world_schema, stat_count=2)
    return eng

def test_engine_initialization(engine):
    assert engine.state.world_name == "Test World"
    assert len(engine.state.stats) == 2
    assert engine.state.year == 1000
    assert engine.state.day == 1

def test_draw_card_empty(engine):
    assert engine.draw_card() is None

def test_draw_card_immediate(engine):
    card = InfoCard(id="test", title="Test", description="Desc", character="narrator")
    engine.immediate_deque.append(card)
    drawn = engine.draw_card()
    assert drawn == card
    assert len(engine.immediate_deque) == 0

def test_draw_card_deck(engine):
    card = ChoiceCard(
        id="test_choice", title="Choice", description="Desc", character="narrator",
        left=Choice(text="L", calls=[]), right=Choice(text="R", calls=[])
    )
    engine.deque.insert(card)
    drawn = engine.draw_card()
    assert drawn == card

@pytest.mark.asyncio
async def test_fill_week_deck(engine):
    # Mock Writer
    with patch("agents.writer.Writer") as MockWriter:
        mock_writer_instance = MockWriter.return_value

        # Create a batch output
        batch_output = WriterBatchOutput(
            cards=[
                ChoiceCardDef(
                    id="c1", title="C1", description="D1", character="king",
                    left_text="L", right_text="R"
                ),
                ChoiceCardDef(
                    id="c2", title="C2", description="D2", character="king",
                    left_text="L", right_text="R"
                )
            ]
        )
        mock_writer_instance.generate_batch = AsyncMock(return_value=batch_output)

        success = await engine.fill_week_deck(language="en")

        assert success is True
        assert engine.deque.count == 2

        # Verify cards are in the deck
        assert engine.deque.draw().id == "c1"
        assert engine.deque.draw().id == "c2"

@pytest.mark.asyncio
async def test_fill_week_deck_season_start(engine):
    # Set up engine for season start (day 1 is default)
    engine.state.day = 1

    with patch("agents.writer.Writer") as MockWriter:
        mock_writer_instance = MockWriter.return_value

        batch_output = WriterBatchOutput(
            cards=[
                InfoCardDef(id="season_start", title="Spring", description="It is spring", character="narrator"),
                ChoiceCardDef(
                    id="c1", title="C1", description="D1", character="king",
                    left_text="L", right_text="R"
                )
            ]
        )
        mock_writer_instance.generate_batch = AsyncMock(return_value=batch_output)

        success = await engine.fill_week_deck(language="en")

        assert success is True

        # Season card should be in immediate_deque
        assert len(engine.immediate_deque) == 1
        assert engine.immediate_deque[0].id == "season_start"

        # Choice card should be in deck
        assert engine.deque.count == 1
        assert engine.deque.draw().id == "c1"

def test_fill_week_deck_demo(engine):
    engine.fill_week_deck_demo()
    # Demo pool has cards, so deck shouldn't be empty
    assert not engine.deque.is_empty

    # If day 1, should have structural cards in immediate_deque
    if engine.state.day == 1:
        # death cards (2 stats * 2 bounds = 4) + season card + (welcome/reborn)
        # Actually demo logic puts welcome/reborn if elapsed_days=1
        assert len(engine.immediate_deque) > 0

def test_resolve_card(engine):
    # Create a choice card that modifies a stat
    card = ChoiceCard(
        id="test_card",
        title="Test",
        description="Desc",
        character="narrator",
        left=Choice(text="Left", calls=[FunctionCall(name="update_stat", params={"wealth": 10})]),
        right=Choice(text="Right", calls=[])
    )

    # Initial wealth
    engine.state.stats["wealth"] = 50

    result = engine.resolve_card(card, "left")

    assert engine.state.stats["wealth"] == 60
    assert engine.state.day == 2 # Day advances

def test_death_check(engine):
    # Set wealth to 0
    engine.state.stats["wealth"] = 0

    death_info = engine.check_death()
    assert death_info is not None
    assert death_info.cause_stat == "wealth"
    assert death_info.cause_value == 0

def test_handle_death(engine):
    # Manually create death info
    from death.loop import DeathInfo
    death = DeathInfo(
        cause_stat="wealth",
        cause_value=0,
        turn=1,
        life_number=1,
        tags_at_death=[],
        stats_at_death={}
    )

    engine.handle_death(death)

    assert len(engine.immediate_deque) == 1
    assert engine._awaiting_resurrection is True
    assert engine.immediate_deque[0].id.startswith("death_")

def test_resurrection(engine):
    engine._awaiting_resurrection = True
    engine.state.stats["wealth"] = 0

    # Mock resurrect method of death_loop to avoid complexity or just rely on default
    # The default DeathLoop resets stats to 50

    engine.complete_resurrection()

    assert engine._awaiting_resurrection is False
    assert engine.state.stats["wealth"] == 50
    assert engine.state.life_number == 2
    assert engine.state.is_first_day_after_death is True
