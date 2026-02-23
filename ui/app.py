"""World Card AI — Textual application entry point.

``WorldCardApp`` owns the ``GameEngine`` and ``CostTracker`` instances and
provides two public methods the screens use:

- ``on_mount`` — push the ``TitleScreen`` as the initial screen.
- ``start_new_game`` — reset the engine and switch to ``LoadingScreen``.

All screen transitions flow through the app so there is a single place
that holds shared state (engine, cost_tracker, theme choice, language).
"""

from __future__ import annotations

from textual.app import App

from game.cost import CostTracker
from game.engine import GameEngine


class WorldCardApp(App):
    """Root Textual application for World Card AI."""

    TITLE = "World Card AI"
    CSS_PATH = "styles/game.tcss"

    def __init__(self, demo: bool = False) -> None:
        super().__init__()
        self.demo_mode = demo
        self.engine = GameEngine()
        self.cost_tracker = CostTracker()
        self.theme_choice: str = ""
        self.stat_count: int = 4
        self.language: str = "en"

    def on_mount(self) -> None:
        """Show the title / main menu screen on startup."""
        from ui.screens.title import TitleScreen

        self.push_screen(TitleScreen())

    def start_new_game(self, theme: str, stat_count: int, demo: bool, language: str = "en") -> None:
        """Reset engine state and navigate to the loading screen.

        Called by ``TitleScreen`` when the player presses Start or Demo.
        A fresh ``GameEngine`` is created so previous-session state is discarded.
        """
        self.theme_choice = theme
        self.stat_count = stat_count
        self.demo_mode = demo
        self.language = language
        self.engine = GameEngine()

        from ui.screens.loading import LoadingScreen

        self.switch_screen(LoadingScreen())
