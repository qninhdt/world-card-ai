"""Ending screen — displayed when a story-ending plot node fires.

Shows the ending title, flavour text, final stats, and play history.
The player can restart (go back to the title screen) or quit.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import Screen
from textual.widgets import Button, Static

from story.dag import PlotNode


class EndingScreen(Screen):
    BINDINGS = [
        Binding("r", "restart", "Restart"),
        Binding("q", "quit_game", "Quit"),
    ]

    DEFAULT_CSS = """
    EndingScreen {
        align: center middle;
    }
    #ending-box {
        width: 70;
        height: auto;
        padding: 2 4;
        border: double $accent;
        background: $surface;
    }
    #ending-header {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #ending-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    #ending-text {
        text-align: center;
        text-style: italic;
        margin: 1 0;
    }
    #ending-stats {
        margin: 1 0;
        text-align: center;
    }
    #ending-history {
        margin: 1 0;
        text-align: center;
    }
    #ending-prompt {
        text-align: center;
        margin-top: 2;
    }
    """

    def __init__(self, ending_node: PlotNode, **kwargs) -> None:
        super().__init__(**kwargs)
        self.ending_node = ending_node

    def compose(self) -> ComposeResult:
        node = self.ending_node
        engine = self.app.engine
        state = engine.state

        with Center():
            with Vertical(id="ending-box"):
                yield Static("═══  THE END  ═══", id="ending-header")
                yield Static(node.plot_description, id="ending-title")
                yield Static(node.ending_text or "Your story has ended.", id="ending-text")

                stats_text = "  ".join(
                    f"{name}: {val}" for name, val in state.stats.items()
                )
                yield Static(f"Final stats: {stats_text}", id="ending-stats")

                history = f"Total turns: {state.turn}  ·  Lives lived: {state.life_number}  ·  Karma: {len(state.karma)} tags"
                yield Static(history, id="ending-history")

                yield Static(
                    "[R] Play Again    [Q] Quit",
                    id="ending-prompt",
                )

    def action_restart(self) -> None:
        from ui.screens.title import TitleScreen

        self.app.switch_screen(TitleScreen())

    def action_quit_game(self) -> None:
        self.app.exit()
