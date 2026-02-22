from __future__ import annotations

from rich.text import Text
from textual.widget import Widget


class TagBar(Widget):
    DEFAULT_CSS = """
    TagBar {
        height: auto;
        min-height: 2;
        padding: 0 2;
        border-bottom: solid $primary-darken-2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._tags: dict[str, str] = {}

    def set_tags(self, tags: dict[str, str]) -> None:
        self._tags = dict(tags)
        self.refresh()

    def render(self) -> Text:
        text = Text()
        text.append("Tags: ", style="bold")
        
        if not self._tags:
            text.append("None", style="dim italic")
            return text

        first = True
        for tag, desc in self._tags.items():
            if tag.startswith("_"):
                continue  # Skip hidden/internal tags
            if not first:
                text.append(" · ", style="dim")
            first = False
            
            # Show tag name, and hover tooltip for description (using Rich's tooltip... wait, Textual doesn't support rich tooltips out of the box easily inside a single Text stream, so we'll just format it cleanly)
            # Actually, Textual has a `Tooltip` feature but it applies to Widgets.
            # To keep it simple, we'll append the description in dim text if it's short, or a small [?] if it's long.
            # Let's just print `Tag (desc)` format, trimming description if needed.
            
            desc_text = desc
            if len(desc_text) > 30:
                desc_text = desc_text[:27] + "..."
            elif not desc_text or desc_text == "No description":
                desc_text = ""
                
            if desc_text:
                text.append(tag, style="bold cyan")
                text.append(f" ({desc_text})", style="dim italic cyan")
            else:
                text.append(tag, style="bold cyan")

        return text
