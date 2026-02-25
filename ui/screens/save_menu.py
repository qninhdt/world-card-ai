"""Load-World screen — lets the player pick an auto-save to resume.

Opened from the title screen via the "📂 Load World" button.  The screen is
read-only (no manual saving): it lists all auto-saves found in ``saves/``,
lets the player load one (switching straight to ``GameScreen``) or delete it
after confirmation.

Layout
------
  ┌──────────────────────────────────────────┐
  │  ◆  Load a World  ◆                       │
  │  ┌────────────────────────────────────┐   │
  │  │  World Name         Day 42 · Life 2│   │
  │  │  Saved 2026-02-23 16:00 UTC        │   │
  │  └────────────────────────────────────┘   │
  │  ... more saves ...                       │
  │  [Load]  [Delete]  [Cancel]               │
  └──────────────────────────────────────────┘
"""

from __future__ import annotations

from datetime import datetime, timezone

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, ListItem, ListView, Static

from game.save import SaveManager, SaveMeta


class SaveMenuScreen(Screen):
    """Load-only save management overlay."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
    ]

    DEFAULT_CSS = """
    SaveMenuScreen {
        align: center middle;
        background: $background 60%;
    }
    #save-box {
        width: 64;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        border: heavy $accent;
        background: $surface;
    }
    #save-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #save-list {
        height: auto;
        max-height: 24;
        border: solid $primary-darken-2;
        margin-bottom: 1;
    }
    .save-item {
        height: 3;
        padding: 0 1;
    }
    .save-item-world {
        text-style: bold;
    }
    .save-item-meta {
        color: $text-muted;
    }
    #no-saves {
        text-align: center;
        color: $text-muted;
        padding: 1;
    }
    #confirm-row {
        height: auto;
        margin-bottom: 1;
        display: none;
    }
    #confirm-row.visible {
        display: block;
    }
    #confirm-label {
        color: $warning;
        text-align: center;
        height: auto;
        margin-bottom: 1;
    }
    #action-row {
        height: auto;
        align-horizontal: center;
    }
    #action-row Button {
        margin: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._saves: list[SaveMeta] = []
        self._selected_slug: str | None = None
        self._confirm_delete: bool = False

    def compose(self) -> ComposeResult:
        self._saves = SaveManager.list_saves()

        with Vertical(id="save-box"):
            yield Static("◆  Load a World  ◆", id="save-title")

            if not self._saves:
                yield Static("No saved worlds found.", id="no-saves")
            else:
                items = []
                for meta in self._saves:
                    items.append(self._make_list_item(meta))
                yield ListView(*items, id="save-list")

            # Confirm-delete row (hidden by default)
            with Vertical(id="confirm-row"):
                yield Static("", id="confirm-label")

            with Horizontal(id="action-row"):
                yield Button("📂 Load", id="btn-load", variant="primary", disabled=True)
                yield Button("🗑  Delete", id="btn-delete", variant="warning", disabled=True)
                yield Button("Cancel", id="btn-cancel", variant="default")

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _make_list_item(meta: SaveMeta) -> ListItem:
        """Build a ListItem widget from a SaveMeta."""
        try:
            dt = datetime.fromisoformat(meta.saved_at)
            # Convert to local time for display
            date_str = dt.astimezone().strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = meta.saved_at[:16] if meta.saved_at else "unknown date"

        days_str = f"Day {meta.elapsed_days}"
        life_str = f"Life {meta.life_number}"

        item = ListItem(
            Static(
                f"[bold]{meta.world_name}[/bold]",
                classes="save-item-world",
            ),
            Static(
                f"{days_str} · {life_str} · Saved {date_str}",
                classes="save-item-meta",
            ),
            classes="save-item",
        )
        # Tag the item with the slug so we can find it on selection
        item.data = meta.world_slug  # type: ignore[attr-defined]
        return item

    def _set_selection(self, slug: str | None) -> None:
        """Update internal selection state and button availability."""
        self._selected_slug = slug
        self._confirm_delete = False
        confirm_row = self.query_one("#confirm-row")
        confirm_row.remove_class("visible")

        has_sel = slug is not None
        self.query_one("#btn-load", Button).disabled = not has_sel
        self.query_one("#btn-delete", Button).disabled = not has_sel
        # Reset delete button label
        self.query_one("#btn-delete", Button).label = "🗑  Delete"

    # ── Event handlers ────────────────────────────────────────────────────

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        slug: str | None = getattr(item, "data", None)
        self._set_selection(slug)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "btn-cancel":
            self.action_close()

        elif btn_id == "btn-load":
            self._do_load()

        elif btn_id == "btn-delete":
            if not self._confirm_delete:
                # First press: ask for confirmation
                self._confirm_delete = True
                slug = self._selected_slug or ""
                label = self.query_one("#confirm-label", Static)
                label.update(f'Delete save for "{slug}"? Press again to confirm.')
                confirm_row = self.query_one("#confirm-row")
                confirm_row.add_class("visible")
                self.query_one("#btn-delete", Button).label = "⚠ Confirm Delete"
            else:
                self._do_delete()

    # ── Actions ───────────────────────────────────────────────────────────

    def _do_load(self) -> None:
        if not self._selected_slug:
            return
        try:
            save_data = SaveManager.load_save(self._selected_slug)
        except Exception as exc:
            self.query_one("#confirm-label", Static).update(
                f"[red]Failed to load: {exc}[/red]"
            )
            self.query_one("#confirm-row").add_class("visible")
            return

        self.app.load_game(save_data)

    def _do_delete(self) -> None:
        if not self._selected_slug:
            return
        SaveManager.delete_save(self._selected_slug)
        slug = self._selected_slug
        self._selected_slug = None
        self._confirm_delete = False

        # Refresh save list
        self._saves = SaveManager.list_saves()
        try:
            lv = self.query_one("#save-list", ListView)
            # Remove the deleted item
            for item in list(lv.children):
                if getattr(item, "data", None) == slug:
                    item.remove()
                    break
            if len(self._saves) == 0:
                lv.remove()
                box = self.query_one("#save-box", Vertical)
                box.mount(Static("No saved worlds found.", id="no-saves"), before=lv)
        except Exception:
            pass

        # Reset buttons
        self.query_one("#btn-load", Button).disabled = True
        self.query_one("#btn-delete", Button).disabled = True
        self.query_one("#btn-delete", Button).label = "🗑  Delete"
        confirm_row = self.query_one("#confirm-row")
        confirm_row.remove_class("visible")

    def action_close(self) -> None:
        self.dismiss()
