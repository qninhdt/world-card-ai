"""Tests for game.save — SaveManager and engine round-trip."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from game.save import SaveManager, SaveMeta, world_to_slug


# ── world_to_slug ─────────────────────────────────────────────────────────────


class TestWorldToSlug:
    def test_basic(self) -> None:
        assert world_to_slug("Medieval Kingdom") == "medieval_kingdom"

    def test_strips_special_chars(self) -> None:
        assert world_to_slug("Cyberpunk Megacity!") == "cyberpunk_megacity"

    def test_empty_returns_world(self) -> None:
        assert world_to_slug("") == "world"

    def test_numbers_preserved(self) -> None:
        assert world_to_slug("World 2099") == "world_2099"


# ── SaveManager (filesystem) ──────────────────────────────────────────────────


@pytest.fixture()
def save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect SaveManager to use a temp directory."""
    import game.save as save_module

    monkeypatch.setattr(save_module, "_SAVES_DIR", tmp_path)
    return tmp_path


def _minimal_save_data() -> dict:
    return {
        "state": {
            "world_name": "Test World",
            "world_context": "",
            "era": "",
            "player": {"id": "player", "name": "Hero", "role": "knight", "description": ""},
            "stats": {"health": 50},
            "stat_defs": [],
            "stat_count": 1,
            "tags": [],
            "tag_defs": [],
            "day": 1,
            "season_index": 0,
            "year": 1,
            "start_day": 1,
            "start_season_index": 0,
            "start_year": 1,
            "seasons": [],
            "turn": 0,
            "npcs": [],
            "relationships": [],
            "pending_plot_node": None,
            "karma": [],
            "life_number": 1,
            "resurrection_mechanic": "",
            "resurrection_flavor": "",
            "previous_life_tags": [],
            "is_first_day_after_death": False,
            "welcome_card": None,
            "reborn_card": None,
            "season_start_card": None,
            "pending_death_cards": {},
        },
        "events": [],
        "dag_fired_nodes": [],
    }


class TestAutosave:
    def test_file_is_created(self, save_dir: Path) -> None:
        data = _minimal_save_data()
        path = SaveManager.autosave("test_world", data)
        assert path.exists()
        assert path.suffix == ".json"

    def test_file_contains_required_keys(self, save_dir: Path) -> None:
        data = _minimal_save_data()
        path = SaveManager.autosave("test_world", data)
        saved = json.loads(path.read_text())
        assert "saved_at" in saved
        assert "save_version" in saved
        assert "state" in saved
        assert "events" in saved
        assert "dag_fired_nodes" in saved

    def test_overwrites_existing(self, save_dir: Path) -> None:
        data = _minimal_save_data()
        SaveManager.autosave("test_world", data)
        data2 = _minimal_save_data()
        data2["state"]["life_number"] = 3
        SaveManager.autosave("test_world", data2)
        # Only one file should exist
        files = list(save_dir.glob("*.json"))
        assert len(files) == 1
        saved = json.loads(files[0].read_text())
        assert saved["state"]["life_number"] == 3


class TestLoadSave:
    def test_roundtrip(self, save_dir: Path) -> None:
        data = _minimal_save_data()
        SaveManager.autosave("test_world", data)
        loaded = SaveManager.load_save("test_world")
        assert loaded["state"]["world_name"] == "Test World"

    def test_missing_raises(self, save_dir: Path) -> None:
        with pytest.raises(FileNotFoundError):
            SaveManager.load_save("nonexistent")


class TestListSaves:
    def test_empty_dir(self, save_dir: Path) -> None:
        assert SaveManager.list_saves() == []

    def test_returns_metas(self, save_dir: Path) -> None:
        SaveManager.autosave("alpha", _minimal_save_data())
        metas = SaveManager.list_saves()
        assert len(metas) == 1
        assert isinstance(metas[0], SaveMeta)
        assert metas[0].world_slug == "alpha"
        assert metas[0].world_name == "Test World"

    def test_sorted_newest_first(self, save_dir: Path) -> None:
        import time

        SaveManager.autosave("first", _minimal_save_data())
        time.sleep(0.01)  # ensure different timestamps
        SaveManager.autosave("second", _minimal_save_data())
        metas = SaveManager.list_saves()
        # Newest (second) should be first
        assert metas[0].world_slug == "second"


class TestDeleteSave:
    def test_deletes_file(self, save_dir: Path) -> None:
        SaveManager.autosave("test_world", _minimal_save_data())
        assert (save_dir / "test_world.json").exists()
        SaveManager.delete_save("test_world")
        assert not (save_dir / "test_world.json").exists()

    def test_noop_if_missing(self, save_dir: Path) -> None:
        # Should not raise
        SaveManager.delete_save("nonexistent")


# ── Engine round-trip ─────────────────────────────────────────────────────────


class TestEngineRoundtrip:
    def test_save_load_preserves_state(self, save_dir: Path) -> None:
        from game.demo import get_demo_world
        from game.engine import GameEngine

        engine = GameEngine()
        world = get_demo_world()
        engine.build_from_schema(world, stat_count=4)

        # Mutate some state
        engine.state.stats = {k: 42 for k in engine.state.stats}
        engine.state.life_number = 3
        engine.state.year = 2

        data = engine.to_save_dict()
        assert "state" in data
        assert "events" in data
        assert "dag_fired_nodes" in data

        # Restore into a fresh engine
        engine2 = GameEngine()
        engine2.load_from_save(data)

        assert engine2.state.world_name == engine.state.world_name
        assert engine2.state.life_number == 3
        assert engine2.state.year == 2
        for stat_id, val in engine2.state.stats.items():
            assert val == 42

    def test_deck_cleared_after_load(self) -> None:
        from game.demo import get_demo_world
        from game.engine import GameEngine

        engine = GameEngine()
        world = get_demo_world()
        engine.build_from_schema(world, stat_count=4)
        engine.prepare_demo_week()

        data = engine.to_save_dict()

        engine2 = GameEngine()
        engine2.load_from_save(data)

        assert engine2.deque.is_empty
        assert len(engine2.immediate_deque) == 0
