"""CardView widget — renders the current card in the centre of the game screen.

Three visual modes:
  Normal choice card  — title panel + left/right swipe prompts with stat previews.
  Info card           — title panel + single dismiss prompt (no choices).
  Story card          — dramatic full-panel style for death / reborn / welcome
                        events, selected via ``set_story_card()``.

Stat effect indicators in the choice labels use ≤ 3 symbols to show magnitude:
  ``[stat: +]`` / ``[stat: +++]`` / ``[stat: ---]``
"""

from __future__ import annotations

from rich.align import Align
from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from textual.widget import Widget

from typing import Any

from cards.models import Card

SOURCE_STYLES: dict[str, str] = {
    "common": "bright_white",
    "plot": "bold red",
    "event": "bold yellow",
    "info": "bold cyan",
    "nested": "bold magenta",
}

SOURCE_BORDER: dict[str, str] = {
    "common": "bright_black",
    "plot": "red",
    "event": "yellow",
    "info": "cyan",
    "nested": "magenta",
}

# Story card styles (death/reborn/welcome)
STORY_STYLES = {
    "death": {"title_color": "bold red", "border": "bright_red", "subtitle": "[bold red]☠ DEATH ☠[/]", "dismiss": "red"},
    "reborn": {"title_color": "bold green", "border": "bright_green", "subtitle": "[bold green]✦ REBIRTH ✦[/]", "dismiss": "green"},
    "welcome": {"title_color": "bold yellow", "border": "bright_yellow", "subtitle": "[bold yellow]★ WELCOME ★[/]", "dismiss": "yellow"},
}


class CardView(Widget):
    DEFAULT_CSS = """
    CardView {
        width: 1fr;
        padding: 1 2;
        align: center middle;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._card: Card | None = None
        self._left_effects: dict[str, int] = {}
        self._right_effects: dict[str, int] = {}
        self._highlight: str | None = None
        self._is_info: bool = False
        self._story_type: str | None = None  # "death", "reborn", "welcome", or None

    def set_card(
        self,
        card: Card | None,
    ) -> None:
        self._card = card
        self._highlight = None
        self._is_info = False
        self._story_type = None
        self._left_effects = self._extract_stat_effects(card.left.calls) if card and hasattr(card, "left") else {}
        self._right_effects = self._extract_stat_effects(card.right.calls) if card and hasattr(card, "right") else {}
        self.refresh()

    def _extract_stat_effects(self, calls: list[Any]) -> dict[str, int]:
        effects: dict[str, int] = {}
        for call in calls:
            if getattr(call, "name", "") == "update_stat":
                params = getattr(call, "params", {})
                if "stat_id" in params and "delta" in params:
                    stat_id = params["stat_id"]
                    delta = params["delta"]
                    effects[stat_id] = effects.get(stat_id, 0) + int(delta)
                else:
                    for stat_id, delta in params.items():
                        if isinstance(delta, (int, float)):
                            effects[stat_id] = effects.get(stat_id, 0) + int(delta)
        return effects

    def set_info_card(self, card: Card) -> None:
        """Set an info card — read-only, no choices."""
        self._card = card
        self._left_effects = {}
        self._right_effects = {}
        self._highlight = None
        self._is_info = True
        self._story_type = None
        self.refresh()

    def set_story_card(self, card: Card, story_type: str) -> None:
        """Set a story card (death/reborn/welcome) with special styling."""
        self._card = card
        self._left_effects = {}
        self._right_effects = {}
        self._highlight = None
        self._is_info = True
        self._story_type = story_type
        self.refresh()

    def set_highlight(self, direction: str | None) -> None:
        self._highlight = direction
        self.refresh()

    def render(self) -> Group | Panel:
        if not self._card:
            return Panel(
                Align.center(Text("\nShuffling the deck...\n", style="dim italic")),
                border_style="bright_black",
                padding=(2, 4),
            )

        card = self._card

        # Story cards get special styling
        if self._story_type and self._story_type in STORY_STYLES:
            return self._render_story(card, self._story_type)

        color = SOURCE_STYLES.get(card.source, "bright_white")
        border = SOURCE_BORDER.get(card.source, "bright_black")

        body = Text(justify="center")
        body.append("\n")
        body.append(card.description, style="italic")
        body.append("\n\n")
        body.append(f"— {card.character}", style="dim")
        body.append("\n")

        subtitle = ""
        if card.source == "plot":
            subtitle = "[bold red]PLOT[/]"
        elif card.source == "event":
            subtitle = "[bold yellow]EVENT[/]"
        elif card.source == "info":
            subtitle = "[bold cyan]INFO[/]"

        panel = Panel(
            Align.center(body),
            title=f"[bold {color}]{card.title}[/]",
            subtitle=subtitle,
            border_style=border,
            padding=(1, 3),
            expand=True,
        )

        if self._is_info:
            # Info card: single dismiss prompt
            dismiss = Text(justify="center")
            dismiss.append("\n")
            dismiss.append("  Press ← or → to continue  ", style="bold cyan dim")
            dismiss.append("\n")
            return Group(panel, dismiss)

        # Choice card: show left/right options
        choices = Text()
        choices.append("\n")
        self._render_choice(choices, "left", "← A", card.left.text)
        choices.append("\n")
        self._render_choice(choices, "right", "D →", card.right.text)
        choices.append("\n")

        return Group(panel, choices)

    def _render_story(self, card: Card, story_type: str) -> Group:
        """Render a story card (death/reborn/welcome) with dramatic styling."""
        style = STORY_STYLES[story_type]

        body = Text(justify="center")
        body.append("\n\n")
        body.append(card.description, style="bold italic")
        body.append("\n\n")
        if card.character and card.character != "narrator":
            body.append(f"— {card.character}", style="dim")
            body.append("\n")
        body.append("\n")

        panel = Panel(
            Align.center(body),
            title=f"[{style['title_color']}]{card.title}[/]",
            subtitle=style["subtitle"],
            border_style=style["border"],
            padding=(2, 4),
            expand=True,
        )

        dismiss = Text(justify="center")
        dismiss.append("\n")
        dismiss_color = style["dismiss"]
        dismiss.append(f"  Press ← or → to continue  ", style=f"bold {dismiss_color}")
        dismiss.append("\n")

        return Group(panel, dismiss)

    def _render_choice(
        self,
        text: Text,
        direction: str,
        key_label: str,
        choice_text: str,
    ) -> None:
        hl = self._highlight == direction
        key_style = "bold reverse cyan" if hl else "bold cyan"
        choice_style = "bold reverse" if hl else ""

        text.append(f"  [{key_label}] ", style=key_style)
        text.append(choice_text, style=choice_style)

        # Show stat preview
        effects = self._left_effects if direction == "left" else self._right_effects
        if effects:
            text.append("  ")
            for stat_id, delta in effects.items():
                if delta == 0:
                    continue
                color = "green" if delta > 0 else "red"
                symbol = "+" if delta > 0 else "-"
                # Determine how many symbols based on magnitude (e.g. <10 is 1, 10-20 is 2, >20 is 3)
                count = min(3, max(1, abs(delta) // 10))
                indicator = symbol * count
                text.append(f"[{stat_id}: {indicator}] ", style=f"bold {color}")
