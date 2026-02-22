"""Timeline widget — compact status bar at the bottom of the game screen.

Shows (left to right):
  World name  ·  Season icon + name  [season progress bar]  Day N, Year Y  ·  elapsed  ·  Life #N

The season progress bar uses 4 block characters representing the 4 weeks:
  ░ = future week,  ▒/▓ = current week (early/late),  █ = completed week.
"""

from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

from game.state import DAYS_PER_WEEK, WEEKS_PER_SEASON


class Timeline(Widget):
    DEFAULT_CSS = """
    Timeline {
        width: 1fr;
        height: 3;
        content-align: left middle;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._day: int = 1
        self._season_name: str = ""
        self._season_icon: str = ""
        self._year: int = 1
        self._week: int = 1
        self._life: int = 1
        self._elapsed_days: int = 0
        self._world_name: str = ""

    def set_data(
        self,
        day: int,
        season_name: str,
        season_icon: str,
        year: int,
        week: int,
        life: int,
        elapsed_days: int,
        world_name: str = "",
    ) -> None:
        self._day = day
        self._season_name = season_name
        self._season_icon = season_icon
        self._year = year
        self._week = week
        self._life = life
        self._elapsed_days = elapsed_days
        self._world_name = world_name
        self.refresh()

    def render(self) -> Text:
        text = Text()
        if self._world_name:
            text.append(f"{self._world_name}", style="bold")
            text.append("  ·  ", style="dim")

        # Season with icon
        if self._season_name:
            text.append(f"{self._season_icon} {self._season_name}", style="bold green")
        else:
            text.append("—", style="dim")

        text.append("  ", style="dim")

        # Season progress bar: 4 rects for 4 weeks
        for w in range(1, WEEKS_PER_SEASON + 1):
            if w < self._week:
                text.append("█", style="green")
            elif w == self._week:
                # Partially filled current week
                day_in_week = ((self._day - 1) % DAYS_PER_WEEK) + 1
                if day_in_week > DAYS_PER_WEEK // 2:
                    text.append("▓", style="yellow")
                else:
                    text.append("▒", style="yellow")
            else:
                text.append("░", style="bright_black")

        text.append("  ", style="dim")

        # Date display
        text.append(f"Day {self._day}", style="")
        text.append(f", Year {self._year}", style="dim")
        text.append("  ·  ", style="dim")

        # Elapsed
        text.append(f"{self._elapsed_days}d", style="dim italic")

        text.append("  ·  ", style="dim")
        if self._life > 1:
            text.append(f"Life #{self._life}", style="bold magenta")
        else:
            text.append(f"Life #{self._life}", style="dim")

        return text
