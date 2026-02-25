from __future__ import annotations

from rich.text import Text
from textual.widget import Widget


class DeckCounter(Widget):
    """Shows deque status and AI generation state."""

    DEFAULT_CSS = """
    DeckCounter {
        width: auto;
        min-width: 24;
        height: 3;
        content-align: right middle;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._cur: int = 0
        self._cap: int = 0
        self._is_generating: bool = False

    def set_status(
        self,
        cur: int,
        cap: int,
        is_generating: bool = False,
    ) -> None:
        self._cur = cur
        self._cap = cap
        self._is_generating = is_generating
        self.refresh()

    def render(self) -> Text:
        text = Text()

        if self._is_generating:
            text.append("[AI writing", style="bold yellow")
            text.append("...]  ", style="dim yellow")

        text.append("Deck ", style="dim")

        cap = self._cap or 1
        cur = self._cur

        bar_width = min(cap, 10)
        filled = round(cur / cap * bar_width)
        filled = max(0, min(bar_width, filled))

        threshold = cap // 2
        if cur <= threshold:
            bar_color = "yellow"
        else:
            bar_color = "cyan"

        text.append("█" * filled, style=bar_color)
        text.append("░" * (bar_width - filled), style="bright_black")
        display_cap = max(cap, cur)
        text.append(f" {cur}/{display_cap}", style=f"bold {bar_color}")

        return text
