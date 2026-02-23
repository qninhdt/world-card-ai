"""StatsBar widget — displays all player stats as icon + bar + value columns.

Each stat renders as:  ``<icon> <name> ████░░░░ <value>``

An optional preview overlay (used when the player hovers over a card choice)
shows green/red deltas next to the current value so the player can see the
consequences of each swipe before committing.
"""

from __future__ import annotations

from rich.columns import Columns
from rich.text import Text
from textual.widget import Widget

from game.state import StatDefinition

# chars per stat cell: icon(2) + name(10) + space(1) + bar(8) + space(1) + val(3) = 25
_BAR_WIDTH = 8
_NAME_MAX = 10


class StatsBar(Widget):
    DEFAULT_CSS = """
    StatsBar {
        height: auto;
        min-height: 4;
        max-height: 8;
        padding: 1 2;
        border-bottom: solid $primary-darken-2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._stats: dict[str, int] = {}
        self._stat_defs: list[StatDefinition] = []
        self._preview: dict[str, int] = {}

    def set_stats(self, stats: dict[str, int], stat_defs: list[StatDefinition]) -> None:
        """Update the stat values and definitions, then refresh the widget."""
        self._stats = dict(stats)
        self._stat_defs = list(stat_defs)
        self._preview = {}
        self.refresh()

    def set_preview(self, effects: dict[str, int]) -> None:
        """Show delta indicators on top of current values (e.g. on card hover)."""
        self._preview = dict(effects)
        self.refresh()

    def clear_preview(self) -> None:
        """Remove any preview deltas and refresh."""
        self._preview = {}
        self.refresh()

    def render(self) -> Columns | Text:
        if not self._stats:
            return Text("No stats loaded", style="dim")

        items = [
            self._render_stat(
                self._icon_for(stat_id),
                self._name_for(stat_id),
                val,
                self._preview.get(stat_id, 0),
            )
            for stat_id, val in self._stats.items()
        ]

        # equal=True forces each column to be the same width; padding between cols
        return Columns(items, equal=True, expand=True, padding=(0, 2))

    def _icon_for(self, stat_id: str) -> str:
        for sd in self._stat_defs:
            if sd.id == stat_id:
                return sd.icon
        return "?"

    def _name_for(self, stat_id: str) -> str:
        for sd in self._stat_defs:
            if sd.id == stat_id:
                return sd.name
        return stat_id

    @staticmethod
    def _render_stat(icon: str, name: str, val: int, preview: int = 0) -> Text:
        name_display = name[:_NAME_MAX].ljust(_NAME_MAX)

        filled = round(val / 100 * _BAR_WIDTH)
        filled = max(0, min(_BAR_WIDTH, filled))
        bar_color = _val_color(val)
        val_style = _val_style(val)

        text = Text(no_wrap=True)
        text.append(f"{icon} ", style="bold")
        text.append(f"{name_display} ", style="bold")
        text.append("█" * filled, style=bar_color)
        text.append("░" * (_BAR_WIDTH - filled), style="bright_black")
        text.append(f" {val:>3d}", style=val_style)

        if preview:
            sign = "+" if preview > 0 else ""
            color = "green" if preview > 0 else "red"
            text.append(f"({sign}{preview})", style=color)

        return text


def _val_color(val: int) -> str:
    if val <= 15 or val >= 85:
        return "red"
    if val <= 25 or val >= 75:
        return "yellow"
    return "green"


def _val_style(val: int) -> str:
    if val <= 15 or val >= 85:
        return "bold red"
    if val <= 25 or val >= 75:
        return "yellow"
    return "green"
