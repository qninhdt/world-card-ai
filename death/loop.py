"""Death detection and resurrection system.

``DeathLoop`` is stateless — both methods take a ``GlobalBlackboard`` and
either read from it (``check_death``) or mutate it (``resurrect``).

Death occurs when any stat reaches 0 (depleted) or 100 (overloaded).
Resurrection carries non-temporary tags forward as *karma* and resets all
other transient state so the player starts a new life with history intact.
"""

from __future__ import annotations

from pydantic import BaseModel

from game.state import GlobalBlackboard


class DeathInfo(BaseModel):
    """Snapshot of the game state at the moment of death."""

    cause_stat: str          # ID of the stat that crossed a boundary
    cause_value: int         # The boundary value (0 = depleted, 100 = overloaded)
    turn: int                # Turn number within the current week
    life_number: int         # Which life this was (1-based)
    tags_at_death: list[str] # Tags held when death occurred
    stats_at_death: dict[str, int]  # Stat values at the moment of death


class DeathLoop:
    """Stateless helper for death detection and resurrection."""

    @staticmethod
    def check_death(state: GlobalBlackboard) -> DeathInfo | None:
        """Return a ``DeathInfo`` if any stat is at 0 or 100, else None."""
        for stat_id, value in state.stats.items():
            if value <= 0:
                return DeathInfo(
                    cause_stat=stat_id,
                    cause_value=0,
                    turn=state.turn,
                    life_number=state.life_number,
                    tags_at_death=list(state.tags),
                    stats_at_death=dict(state.stats),
                )
            if value >= 100:
                return DeathInfo(
                    cause_stat=stat_id,
                    cause_value=100,
                    turn=state.turn,
                    life_number=state.life_number,
                    tags_at_death=list(state.tags),
                    stats_at_death=dict(state.stats),
                )
        return None

    @staticmethod
    def resurrect(state: GlobalBlackboard) -> list[str]:
        """Reset state for a new life and return the karma tags carried forward.

        Karma = non-temporary tags (anything not prefixed with ``_temp``), capped
        at 10.  Karma is added to ``state.karma`` for historical tracking and
        kept in ``state.tags`` so the new life starts with those modifiers.

        Stats are reset to 50 and the NPC appearance counters are zeroed so the
        Writer produces a fresh distribution of card characters.
        """
        important_tags = [t for t in state.tags if not t.startswith("_temp")]
        karma = important_tags[:10]

        state.previous_life_tags = karma.copy()
        state.karma.extend(karma)
        state.life_number += 1

        # Keep karma tags
        state.tags = set(karma)

        # Reset stats to 50
        for stat_id in state.stats:
            state.stats[stat_id] = 50

        # Reset NPC appearances
        for npc in state.npcs:
            npc.npc_appearance_count = 0

        # Skip time to next season
        from game.state import SEASONS_PER_YEAR
        state.season_index = (state.season_index + 1) % SEASONS_PER_YEAR
        if state.season_index == 0:
            state.year += 1
            
        state.day = 1
        state.turn = 0

        return karma
