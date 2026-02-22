from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

from game.cost import CostTracker


class CostDisplay(Widget):
    DEFAULT_CSS = """
    CostDisplay {
        width: auto;
        min-width: 16;
        height: 3;
        content-align: right middle;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tracker: CostTracker | None = None
        self._demo_mode: bool = False

    def set_tracker(self, tracker: CostTracker, demo_mode: bool = False) -> None:
        self._tracker = tracker
        self._demo_mode = demo_mode
        self.refresh()

    def update_display(self) -> None:
        self.refresh()

    def render(self) -> Text:
        text = Text()

        if self._demo_mode:
            text.append("demo", style="dim italic")
            return text

        if not self._tracker or not self._tracker.entries:
            text.append("Cost: ", style="dim")
            text.append("$-.----", style="dim")
            return text

        t = self._tracker
        text.append("Cost: ", style="dim")

        cost = t.total_cost
        if cost < 0.001:
            style = "dim green"
        elif cost < 0.05:
            style = "green"
        elif cost < 0.20:
            style = "yellow"
        else:
            style = "bold red"
        text.append(f"${cost:.4f}", style=style)

        tokens = t.total_tokens
        if tokens > 0:
            text.append(f" {tokens}tok", style="dim")

        return text
