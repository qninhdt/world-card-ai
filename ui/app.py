from __future__ import annotations

from textual.app import App

from game.cost import CostTracker
from game.engine import GameEngine


class WorldCardApp(App):
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
        from ui.screens.title import TitleScreen

        self.push_screen(TitleScreen())

    def start_new_game(self, theme: str, stat_count: int, demo: bool, language: str = "en") -> None:
        self.theme_choice = theme
        self.stat_count = stat_count
        self.demo_mode = demo
        self.language = language
        self.engine = GameEngine()

        from ui.screens.loading import LoadingScreen

        self.switch_screen(LoadingScreen())
