from __future__ import annotations

from pydantic import BaseModel

from game.state import GlobalBlackboard


class DeathInfo(BaseModel):
    cause_stat: str  # stat id
    cause_value: int  # 0 or 100
    turn: int
    life_number: int
    tags_at_death: list[str]
    stats_at_death: dict[str, int]


class DeathLoop:

    @staticmethod
    def check_death(state: GlobalBlackboard) -> DeathInfo | None:
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
        """Reset world state for a new life. Keep tags (as karma) + DAG state."""
        important_tags = [t for t in state.tags if not t.startswith("_temp")]
        karma = important_tags[:10]

        state.previous_life_tags = karma.copy()
        state.karma.extend(karma)
        state.life_number += 1
        state.turn = 0

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
