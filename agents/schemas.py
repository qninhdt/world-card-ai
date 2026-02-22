from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


# ── Function Call ───────────────────────────────────────────────────────────


class FunctionCall(BaseModel):
    """A single game function call produced by the AI."""

    name: str = Field(description="Function name from the registry")
    params: dict = Field(default_factory=dict, description="Function-specific parameters")


# ── Stat ────────────────────────────────────────────────────────────────────


class StatDef(BaseModel):
    id: str = Field(description="Snake_case unique identifier (English), e.g. 'treasury'")
    name: str = Field(description="Display name, e.g. 'Treasury'")
    description: str = Field(description="What this stat represents in the world")
    icon: str = Field(description="Single character or emoji representing the stat")


# ── Entity (base for Player & NPC) ──────────────────────────────────────────


class EntityDef(BaseModel):
    id: str = Field(description="Snake_case unique identifier (English)")
    name: str = Field(description="Character name")
    role: str = Field(description="Role or title, e.g. 'Court Advisor'")
    description: str = Field(description="Rich character description")
    traits: list[str] = Field(default_factory=list, description="Personality traits")


class PlayerCharacterDef(EntityDef):
    """Player's character identity — generated at world creation."""
    pass


class NPCDef(EntityDef):
    enabled: bool = Field(True, description="If false, NPC cannot appear in actions but exists in context")


# ── Relationship ────────────────────────────────────────────────────────────


class RelationshipDef(BaseModel):
    a: str = Field(description="Entity id — use 'player' for the player character")
    b: str = Field(description="Entity id")
    relationship: str = Field(description="Description of the relationship")


# ── Tags ────────────────────────────────────────────────────────────────────


class TagDef(BaseModel):
    id: str = Field(description="Snake_case unique identifier (English)")
    name: str = Field(description="Display name")
    description: str = Field(description="What this tag represents")


# ── Season ──────────────────────────────────────────────────────────────────


class SeasonDef(BaseModel):
    name: str = Field(description="Season name, e.g. 'Spring', 'Winter'")
    description: str = Field(description="Flavor text for this season")
    icon: str = Field(description="Single emoji")
    on_season_end_calls: list[FunctionCall] = Field(
        default_factory=list,
        description="Function calls to execute when this season ends",
    )
    on_week_end_calls: list[FunctionCall] = Field(
        default_factory=list,
        description="Function calls to execute at the end of each week in this season",
    )


# ── Plot DAG ────────────────────────────────────────────────────────────────


class PlotNodeDef(BaseModel):
    """Description-only plot node. The Writer generates the actual card when it fires."""

    id: str = Field(description="Snake_case unique identifier (English)")
    plot_description: str = Field(
        description="Rich narrative description of what happens at this story point. "
        "The Writer will use this to generate the actual card."
    )
    condition: str = Field(
        "True",
        description="Python expression evaluated with state context (stats, tags, events, season, day, year, elapsed_days). "
        "Example: \"stats['treasury'] > 10 and 'allied' in tags\"",
    )
    calls: list[FunctionCall] = Field(
        default_factory=list,
        description="Function calls to execute when this node fires (e.g. enable_npc, update_stat)",
    )
    next_nodes: list[str] = Field(
        default_factory=list,
        description="IDs of nodes this leads to",
    )
    is_ending: bool = False
    ending_text: str | None = None


# ── World Generation (Architect output) ─────────────────────────────────────


class WorldGenSchema(BaseModel):
    """Complete world generation output from The Architect."""

    world_name: str = Field(description="Name of the world/kingdom/realm")
    world_description: str = Field(description="2-3 sentence world description")
    era: str = Field(description="Time period or era name")
    starting_year: int = Field(
        description="Starting year number",
    )
    resurrection_mechanic: str = Field(default="", description="How the player is reborn after death")
    resurrection_flavor: str = Field(default="", description="Flavor text shown on resurrection")

    player_character: PlayerCharacterDef = Field(
        description="The player's character identity",
    )

    stats: list[StatDef] = Field(
        description="Exactly N stats as requested, thematically tied to the world"
    )

    npcs: list[NPCDef] = Field(
        description="5-8 NPCs (some may start disabled)"
    )

    relationships: list[RelationshipDef] = Field(
        default_factory=list,
        description="Relationships between entities (NPCs and player)",
    )

    tags: list[TagDef] = Field(
        description="All available tags the Writer may use"
    )

    plot_nodes: list[PlotNodeDef] = Field(
        description="A list of plot nodes forming a story DAG with 3-4 endings."
    )

    seasons: list[SeasonDef] = Field(
        description="Exactly 4 seasons of the year (e.g. Spring, Summer, Autumn, Winter)."
    )


# ── Writer Card Definitions ─────────────────────────────────────────────────


class ChoiceCardDef(BaseModel):
    """Choice card definition from the Writer."""

    type: Literal["choice"] = "choice"
    id: str | None = Field(default=None, description="Optional ID (e.g. for special generated cards)")
    title: str
    description: str = Field(description="Card text, 1-3 sentences")
    character: str = Field(description="NPC id who presents this card")
    source: str = Field("common", description="common|plot|event")
    left_text: str = Field(description="Left swipe choice text")
    left_calls: list[FunctionCall] = Field(default_factory=list, description="Function calls for left choice")
    right_text: str = Field(description="Right swipe choice text")
    right_calls: list[FunctionCall] = Field(default_factory=list, description="Function calls for right choice")
    # Tree nested cards (max 2 levels deep, 2^2 = 4 leaf cards)
    tree_left: list[CardDef] = Field(default_factory=list)
    tree_right: list[CardDef] = Field(default_factory=list)


class InfoCardDef(BaseModel):
    """Info card definition from the Writer — read-only, no choices.

    Use next_cards to split long info messages into a chain of cards.
    """

    type: Literal["info"] = "info"
    id: str | None = Field(default=None, description="Optional ID for structural cards (e.g. season_, welcome_, reborn_, death_)")
    title: str
    description: str = Field(description="Card text, 1-3 sentences per card. Split longer messages across next_cards.")
    character: str = Field(description="NPC id or 'narrator'")
    source: str = Field("common", description="common|plot|event")
    next_cards: list[InfoCardDef] = Field(default_factory=list, description="Chain of follow-up info cards if message is long")


CardDef = Annotated[Union[ChoiceCardDef, InfoCardDef], Field(discriminator="type")]

ChoiceCardDef.model_rebuild()
InfoCardDef.model_rebuild()


class WriterBatchOutput(BaseModel):
    """Unified Writer output for any batch generation call."""

    cards: list[CardDef] = Field(
        description="All generated cards: common + job cards in a single list. "
        "Use type='choice' for cards with decisions, type='info' for read-only cards."
    )
