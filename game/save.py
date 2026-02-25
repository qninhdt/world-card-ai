"""Save/load management for World Card AI.

``SaveManager`` writes one JSON file per world to a ``saves/`` directory at
the project root.  Files are keyed by a URL-safe world slug derived from the
world name, so each world has exactly one auto-save slot that is overwritten
on every weekly save.

Public API
----------
list_saves()                  -> list[SaveMeta]
autosave(world_slug, data)    -> Path
load_save(world_slug)         -> dict
delete_save(world_slug)       -> None
world_to_slug(world_name)     -> str
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

# Saves directory — sits next to the project root (relative to this file's
# parent-parent so it works regardless of CWD).
_SAVES_DIR = Path(__file__).parent.parent / "saves"

SAVE_VERSION = 1  # bump if the format changes


# ── Save Metadata ────────────────────────────────────────────────────────────


class SaveMeta(NamedTuple):
    """Lightweight summary of a save file shown in the load menu."""

    world_slug: str
    world_name: str
    saved_at: str   # ISO-8601 string (UTC)
    elapsed_days: int
    life_number: int


# ── Helpers ──────────────────────────────────────────────────────────────────


def world_to_slug(world_name: str) -> str:
    """Convert a world name to a safe lowercase filename stem.

    Examples
    --------
    "Medieval Kingdom" -> "medieval_kingdom"
    "Cyberpunk Megacity!" -> "cyberpunk_megacity"
    """
    slug = world_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug or "world"


def _saves_dir() -> Path:
    """Return (and create) the saves directory."""
    _SAVES_DIR.mkdir(parents=True, exist_ok=True)
    return _SAVES_DIR


# ── SaveManager ──────────────────────────────────────────────────────────────


class SaveManager:
    """Static-style helper class — all methods are class methods."""

    @classmethod
    def list_saves(cls) -> list[SaveMeta]:
        """Return save metadata sorted newest-first."""
        metas: list[SaveMeta] = []
        for path in _saves_dir().glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                state = data.get("state", {})
                metas.append(
                    SaveMeta(
                        world_slug=path.stem,
                        world_name=state.get("world_name", path.stem),
                        saved_at=data.get("saved_at", ""),
                        elapsed_days=cls._elapsed_days(state),
                        life_number=state.get("life_number", 1),
                    )
                )
            except Exception:
                # Corrupt or unrecognised file — skip silently
                continue

        metas.sort(key=lambda m: m.saved_at, reverse=True)
        return metas

    @classmethod
    def autosave(cls, world_slug: str, data: dict) -> Path:
        """Write (or overwrite) the save file for the given world slug.

        ``data`` must be the dict returned by ``GameEngine.to_save_dict()``.
        A ``saved_at`` timestamp and ``save_version`` are injected here.
        Returns the path that was written.
        """
        data = dict(data)  # shallow copy so we don't mutate the caller's dict
        data["saved_at"] = datetime.now(tz=timezone.utc).isoformat()
        data["save_version"] = SAVE_VERSION

        path = _saves_dir() / f"{world_slug}.json"
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=_json_default),
            encoding="utf-8",
        )
        return path

    @classmethod
    def load_save(cls, world_slug: str) -> dict:
        """Parse and return the save dict for *world_slug*.

        Raises ``FileNotFoundError`` if the file does not exist,
        ``json.JSONDecodeError`` if it is malformed.
        """
        path = _saves_dir() / f"{world_slug}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def delete_save(cls, world_slug: str) -> None:
        """Delete the save file for *world_slug* (no-op if missing)."""
        path = _saves_dir() / f"{world_slug}.json"
        path.unlink(missing_ok=True)

    @classmethod
    def save_exists(cls, world_slug: str) -> bool:
        """Return True if a save file exists for the given slug."""
        return (_saves_dir() / f"{world_slug}.json").exists()

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _elapsed_days(state: dict) -> int:
        """Compute elapsed_days from raw state dict (mirrors GlobalBlackboard)."""
        from game.state import DAYS_PER_YEAR, DAYS_PER_SEASON

        year = state.get("year", 1)
        season = state.get("season_index", 0)
        day = state.get("day", 1)
        sy = state.get("start_year", 1)
        ss = state.get("start_season_index", 0)
        sd = state.get("start_day", 1)

        current = year * DAYS_PER_YEAR + season * DAYS_PER_SEASON + day
        start = sy * DAYS_PER_YEAR + ss * DAYS_PER_SEASON + sd
        return max(0, current - start)


# ── JSON helper ──────────────────────────────────────────────────────────────


def _json_default(obj):
    """Fallback serialiser for types that ``json.dumps`` can't handle natively."""
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")
