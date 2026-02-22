"""Runtime game state — the single source of truth during a play session.

``GlobalBlackboard`` is a Pydantic model that holds every piece of mutable
state needed by the engine, agents and UI:

- World metadata (name, era, description)
- Player character and NPC roster
- Stats (keyed by stat ID, 0–100 each)
- Tags (a set of string identifiers carried across actions)
- Time model (day/season/year calendar)
- Structural pre-generated cards waiting to be shown (welcome, reborn, season)
- Karma and resurrection history
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agents.schemas import FunctionCall
from cards.models import Card


# ── Season (runtime) ────────────────────────────────────────────────────────


class Season(BaseModel):
    name: str
    description: str
    icon: str
    on_season_end_calls: list[FunctionCall] = []
    on_week_end_calls: list[FunctionCall] = []
    on_day_end_calls: list[FunctionCall] = []


# ── Entity (runtime) ───────────────────────────────────────────────────────


class Entity(BaseModel):
    id: str
    name: str
    role: str
    description: str
    traits: list[str] = []


class NPC(Entity):
    enabled: bool = True
    npc_appearance_count: int = 0


class PlayerCharacter(Entity):
    pass


# ── Stat ────────────────────────────────────────────────────────────────────


class StatDefinition(BaseModel):
    id: str
    name: str
    description: str
    icon: str


# ── Tag ─────────────────────────────────────────────────────────────────────


class TagDefinition(BaseModel):
    id: str
    name: str
    description: str


# ── Relationship ────────────────────────────────────────────────────────────


class Relationship(BaseModel):
    a: str  # entity id or "player"
    b: str
    relationship: str


# ── Constants ───────────────────────────────────────────────────────────────

DAYS_PER_WEEK = 7
WEEKS_PER_SEASON = 4
DAYS_PER_SEASON = DAYS_PER_WEEK * WEEKS_PER_SEASON  # 28
SEASONS_PER_YEAR = 4
DAYS_PER_YEAR = DAYS_PER_SEASON * SEASONS_PER_YEAR  # 112


# ── Global State ────────────────────────────────────────────────────────────


class GlobalBlackboard(BaseModel):
    # World
    world_name: str = ""
    world_context: str = ""
    era: str = ""

    # Player
    player: PlayerCharacter = PlayerCharacter(id="player", name="", role="", description="")

    # Stats (keyed by stat id)
    stats: dict[str, int] = {}
    stat_defs: list[StatDefinition] = []
    stat_count: int = 4

    # Tags (set of tag ids currently held by the player)
    tags: set[str] = set()

    # Tag definitions (all available tags)
    tag_defs: list[TagDefinition] = []

    # Time — day/season/year model
    day: int = 1            # day within current season (1-28)
    season_index: int = 0   # which season (0-3)
    year: int = 1           # current year
    
    # Starting track to compute elapsed time
    start_day: int = 1
    start_season_index: int = 0
    start_year: int = 1

    # Seasons
    seasons: list[Season] = []

    # Turn tracking (within current week)
    turn: int = 0           # actions this week (0-6)

    # NPCs
    npcs: list[NPC] = []
    relationships: list[Relationship] = []

    # Plot
    pending_plot_node: str | None = None  # checked node id, fires at week end

    # Death / resurrection
    karma: list[str] = []
    life_number: int = 1
    resurrection_mechanic: str = ""
    resurrection_flavor: str = ""
    previous_life_tags: list[str] = []
    is_first_day_after_death: bool = False

    # Structural Info Card Storage
    welcome_card: Card | None = None
    reborn_card: Card | None = None
    season_start_card: Card | None = None
    pending_death_cards: dict[str, Card] = Field(default_factory=dict)

    # ── Helpers ─────────────────────────────────────────────────────────

    def get_stat_icon(self, stat_id: str) -> str:
        """Return the display icon for a stat, or '?' if the stat is unknown."""
        for sd in self.stat_defs:
            if sd.id == stat_id:
                return sd.icon
        return "?"

    def get_stat_name(self, stat_id: str) -> str:
        """Return the display name for a stat, or the raw ID if unknown."""
        for sd in self.stat_defs:
            if sd.id == stat_id:
                return sd.name
        return stat_id

    def get_enabled_npcs(self) -> list[NPC]:
        """Return NPCs that are currently available for card interactions."""
        return [n for n in self.npcs if n.enabled]

    def get_enabled_npc_names(self) -> list[str]:
        """Return the names of all currently enabled NPCs."""
        return [n.name for n in self.get_enabled_npcs()]

    def current_season(self) -> Season | None:
        """Return the active Season object, or None if seasons are not configured."""
        if self.seasons and 0 <= self.season_index < len(self.seasons):
            return self.seasons[self.season_index]
        return None

    @property
    def week_in_season(self) -> int:
        """Current week within the season (1-based, range 1–WEEKS_PER_SEASON)."""
        return ((self.day - 1) // DAYS_PER_WEEK) + 1

    def advance_day(self) -> dict[str, bool]:
        """Advance the calendar by one day and return which boundaries were crossed.

        Returns a dict with boolean flags:
          - ``week_end``   — True if a 7-day week just completed.
          - ``season_end`` — True if a 28-day season just completed.

        When a season boundary is crossed ``season_index`` is automatically
        incremented (and ``year`` incremented when all seasons wrap around).
        """
        self.day += 1
        self.turn += 1

        crossed = {"week_end": False, "season_end": False}

        # Week boundary (every 7 days)
        if self.turn >= DAYS_PER_WEEK:
            crossed["week_end"] = True
            self.turn = 0

        # Season boundary (every 28 days)
        if self.day > DAYS_PER_SEASON:
            crossed["season_end"] = True
            self.day = 1
            self.season_index = (self.season_index + 1) % SEASONS_PER_YEAR
            if self.season_index == 0:
                self.year += 1

        return crossed

    def advance_to_next_season(self) -> None:
        """Skip remaining days in the current season and jump to Day 1 of the next."""
        self.day = 1
        num_seasons = len(self.seasons) if self.seasons else 4
        self.season_index = (self.season_index + 1) % num_seasons
        if self.season_index == 0:
            self.year += 1

    @property
    def elapsed_days(self) -> int:
        """Total days elapsed since the game started (across all lives)."""
        current_abs = (self.year * DAYS_PER_YEAR) + (self.season_index * DAYS_PER_SEASON) + self.day
        start_abs = (self.start_year * DAYS_PER_YEAR) + (self.start_season_index * DAYS_PER_SEASON) + self.start_day
        return current_abs - start_abs

    @property
    def date_display(self) -> str:
        """Human-readable current date string, e.g. 'Day 5, Spring, Year 2'."""
        season = self.current_season()
        season_name = season.name if season else f"Season {self.season_index + 1}"
        return f"Day {self.day}, {season_name}, Year {self.year}"

    @property
    def elapsed_display(self) -> str:
        """Compact elapsed-time string, e.g. '1y 2s 3d' or '5d'."""
        years = self.elapsed_days // DAYS_PER_YEAR
        rem = self.elapsed_days % DAYS_PER_YEAR
        seasons = rem // DAYS_PER_SEASON
        days = rem % DAYS_PER_SEASON
        parts = []
        if years:
            parts.append(f"{years}y")
        if seasons:
            parts.append(f"{seasons}s")
        parts.append(f"{days}d")
        return " ".join(parts)

    def snapshot(self) -> dict:
        """Return a compressed state snapshot used as AI generation context.

        Intentionally minimal — only the fields the Writer and Architect need
        to produce contextually relevant cards.  Do not add large blobs here.
        """
        season = self.current_season()
        return {
            "world": self.world_name,
            "era": self.era,
            "day": self.day,
            "season": season.name if season else "",
            "year": self.year,
            "elapsed_days": self.elapsed_days,
            "week": self.week_in_season,
            "life": self.life_number,
            "stats": self.stats,
            "tags": list(self.tags),
            "karma": self.karma[:10],
            "player": {
                "name": self.player.name,
                "role": self.player.role,
            },
            "npcs": [
                {
                    "id": n.id,
                    "name": n.name,
                    "role": n.role,
                    "enabled": n.enabled,
                    "appearances": n.npc_appearance_count,
                }
                for n in self.npcs
            ],
            "relationships": [
                {"a": r.a, "b": r.b, "relationship": r.relationship}
                for r in self.relationships
            ],
        }
