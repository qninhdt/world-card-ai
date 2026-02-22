"""Title screen — main menu where the player configures and starts a new game.

Lets the player choose:
  - World theme (preset or custom text)
  - Number of stats (3–5)
  - Language (English / Tiếng Việt)
  - Normal mode (requires OPENROUTER_API_KEY) or Demo mode (offline)
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Select, Static


TITLE_ART = r"""
╔═══════════════════════════════════════════╗
║                                           ║
║        ◆  W O R L D   C A R D  ◆          ║
║                                           ║
║                                           ║
║       Survive. Decide. Be Reborn.         ║
║                                           ║
╚═══════════════════════════════════════════╝
"""

THEMES: list[tuple[str, str]] = [
    ("🏰 Medieval Kingdom", "A medieval kingdom of knights, clergy and scheming nobles"),
    ("🌆 Cyberpunk Megacity", "A neon-lit dystopian megacity ruled by corporations and hackers"),
    ("🏴‍☠️ Pirate Empire", "A vast ocean of pirate fleets, hidden islands and naval warfare"),
    ("🧟 Zombie Apocalypse", "A post-apocalyptic wasteland overrun by the undead"),
    ("🚀 Space Colony", "A frontier space station on the edge of known civilisation"),
    ("🧙 Dark Fantasy", "A cursed realm of dark magic, ancient evils and desperate heroes"),
    ("🏛️ Ancient Rome", "The Roman Empire at the height of its power and political intrigue"),
    ("🤖 AI Uprising", "A near-future world where AI systems begin to challenge human control"),
    ("🌋 Volcanic Island", "A remote volcanic island with warring tribes and ancient secrets"),
    ("🎪 Travelling Circus", "A magical travelling circus hiding dark secrets beneath the big top"),
]

LANGUAGES = [
    ("en", "English"),
    ("vi", "Tiếng Việt"),
]


class TitleScreen(Screen):
    BINDINGS = [
        Binding("escape", "quit", "Quit"),
    ]

    DEFAULT_CSS = """
    TitleScreen {
        align: center middle;
    }
    #title-box {
        width: 60;
        height: auto;
        padding: 1 3;
        border: heavy $accent;
        background: $surface;
    }
    #title-art {
        height: auto;
        text-align: center;
        color: $accent;
        text-style: bold;
    }
    #theme-label {
        height: auto;
        margin-top: 1;
    }
    #theme-select {
        width: 100%;
        margin-bottom: 0;
    }
    #custom-input {
        height: auto;
        margin-top: 0;
        margin-bottom: 1;
    }
    #options-row {
        height: auto;
        margin-top: 1;
        margin-bottom: 0;
    }
    #options-left {
        width: 1fr;
        height: auto;
    }
    #options-right {
        width: 22;
        height: auto;
        padding-left: 2;
    }
    .opt-label {
        height: auto;
    }
    .opt-radio {
        height: auto;
        margin-bottom: 1;
    }
    #btn-row {
        height: auto;
        align-horizontal: center;
        margin-top: 1;
        padding-bottom: 1;
    }
    #btn-row Button {
        margin: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        # Build theme options: presets + custom
        theme_options = [(label, desc) for label, desc in THEMES]
        theme_options.append(("✏️  Custom Theme", "__custom__"))

        with Vertical(id="title-box"):
            yield Static(TITLE_ART, id="title-art")

            yield Label("World Theme", id="theme-label")
            yield Select(
                theme_options,
                value=THEMES[0][1],  # Default to first theme
                id="theme-select",
                allow_blank=False,
            )
            yield Input(
                placeholder="Enter custom theme...",
                id="custom-input",
                disabled=True,
            )

            with Horizontal(id="options-row"):
                with Vertical(id="options-left"):
                    yield Label("Number of Stats", classes="opt-label")
                    yield RadioSet(
                        RadioButton("3 Stats"),
                        RadioButton("4 Stats", value=True),
                        RadioButton("5 Stats"),
                        id="stat-radio",
                        classes="opt-radio",
                    )
                with Vertical(id="options-right"):
                    yield Label("Language", classes="opt-label")
                    yield RadioSet(
                        RadioButton("English", value=True),
                        RadioButton("Tiếng Việt"),
                        id="lang-radio",
                        classes="opt-radio",
                    )
            with Horizontal(id="btn-row"):
                yield Button("⚔  New World", id="start-btn", variant="primary")
                yield Button("Demo Mode", id="demo-btn", variant="default")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "theme-select":
            custom_input = self.query_one("#custom-input", Input)
            is_custom = event.value == "__custom__"
            custom_input.disabled = not is_custom
            if is_custom:
                custom_input.focus()

    def _get_theme(self) -> str:
        select = self.query_one("#theme-select", Select)
        if select.value == "__custom__":
            return self.query_one("#custom-input", Input).value.strip()
        return str(select.value) if select.value else THEMES[0][1]

    def _get_stat_count(self) -> int:
        radio = self.query_one("#stat-radio", RadioSet)
        idx = radio.pressed_index
        return (idx + 3) if idx is not None else 4

    def _get_language(self) -> str:
        radio = self.query_one("#lang-radio", RadioSet)
        idx = radio.pressed_index
        return LANGUAGES[idx][0] if idx is not None else "en"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        theme = self._get_theme()
        stat_count = self._get_stat_count()
        lang = self._get_language()

        if event.button.id == "start-btn":
            self.app.start_new_game(theme=theme, stat_count=stat_count, demo=False, language=lang)
        elif event.button.id == "demo-btn":
            self.app.start_new_game(theme=theme, stat_count=stat_count, demo=True, language=lang)

    def action_quit(self) -> None:
        self.app.exit()
