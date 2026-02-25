"""EventsPanel widget — sidebar listing all active in-game events.

Renders each event as:  ``<type-icon> <icon> <name>  \n  <progress>  \n  <description>``

Events are provided as plain dicts via ``set_events()`` (produced by
``engine.get_all_events_for_display()``) so the widget has no dependency on
the engine domain models.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from textual.widget import Widget


class EventsPanel(Widget):
    DEFAULT_CSS = """
    EventsPanel {
        width: 32;
        min-width: 28;
        max-width: 38;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._events: list[dict] = []

    def set_events(self, events: list[dict]) -> None:
        """Accepts event dicts from engine.get_all_events_for_display()."""
        self._events = events
        self.refresh()

    def render(self) -> Panel:
        if not self._events:
            content = Text("No active events", style="dim italic", justify="center")
            return Panel(content, title="[bold]Events[/]", border_style="bright_black", padding=(1, 1))

        combined = Text()
        for i, event in enumerate(self._events):
            if i > 0:
                combined.append("\n")
            combined.append_text(self._render_event(event))

        return Panel(combined, title="[bold]Events[/]", border_style="bright_black", padding=(1, 1))

    @staticmethod
    def _render_event(event: dict) -> Text:
        text = Text()

        icon = event.get("icon", "!")
        name = event.get("name", "Unknown")
        event_type = event.get("type", "")
        progress = event.get("progress", "")
        description = event.get("description", "")

        # Type indicator
        if event_type == "time_based":
            type_style = "bold yellow"
            type_label = "⏱"
        else:
            type_style = "bold cyan"
            type_label = "🔄"

        text.append(f"{type_label} {icon} ", style="bold")
        text.append(name, style=type_style)
        text.append("\n")
        text.append(f"  {progress}", style="dim")
        text.append("\n")
        if description:
            text.append(f"  {description[:40]}", style="dim italic")
            text.append("\n")

        return text
