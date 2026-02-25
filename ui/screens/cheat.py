"""Cheat mode overlay — shows card effects and queued card list."""
from __future__ import annotations

from rich.console import Group
from rich.rule import Rule
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Static

from cards.deck import WeightedDeque
from cards.models import Card, ChoiceCard
from game.state import GlobalBlackboard


_SOURCE_LABEL: dict[str, tuple[str, str]] = {
    "plot":   ("PLOT",    "bold magenta"),
    "event":  ("EVENT",   "bold cyan"),
    "tree":   ("TREE",    "bold yellow"),
    "story":  ("STORY",   "bold green"),
    "common": ("CARD",    "dim"),
}


class CheatScreen(ModalScreen):
    BINDINGS = [
        Binding("c", "dismiss", "Close", show=False),
        Binding("escape", "dismiss", "Close", show=False),
    ]

    DEFAULT_CSS = """
    CheatScreen {
        align: center middle;
    }
    #cheat-container {
        width: 72;
        max-height: 38;
        background: $surface;
        border: double $warning;
        padding: 1 2;
    }
    """

    def __init__(self, card: Card | None, deck: WeightedDeque, state: GlobalBlackboard) -> None:
        super().__init__()
        self._card = card
        self._deck = deck
        self._state = state

    def compose(self) -> ComposeResult:
        with ScrollableContainer(id="cheat-container"):
            yield Static(self._build_renderable())

    def _build_renderable(self) -> object:
        sections: list[object] = []

        # ── Title ────────────────────────────────────────────────────────
        title = Text("⚠  CHEAT MODE  ⚠", style="bold yellow", justify="center")
        sections.append(title)
        sections.append(Text("Press C or ESC to close", style="dim", justify="center"))
        sections.append(Rule(style="yellow"))

        # ── Card info ────────────────────────────────────────────────────
        if self._card:
            sections.append(Text(f"Current card: {self._card.title}", style="bold white"))
            sections.append(Text(f"Type: {self._card.type}  Source: {self._card.source}  Priority: {self._card.priority}", style="dim"))
            sections.append(Text())

            if self._card.type == "info":
                sections.append(Text("  ℹ  Info card — no choices, dismiss only", style="bold cyan"))
            elif isinstance(self._card, ChoiceCard):
                left_label = Text()
                left_label.append("← LEFT  ", style="bold blue")
                left_label.append(f'"{self._card.left.text}"', style="italic")
                sections.append(left_label)
                sections.append(Text(f"  Calls: {len(self._card.left.calls)}", style="dim"))

                if self._card.tree_left:
                    sections.append(Text(f"  ↩ Queues {len(self._card.tree_left)} tree card(s)", style="green"))

                sections.append(Text())

                right_label = Text()
                right_label.append("→ RIGHT  ", style="bold red")
                right_label.append(f'"{self._card.right.text}"', style="italic")
                sections.append(right_label)
                sections.append(Text(f"  Calls: {len(self._card.right.calls)}", style="dim"))

                if self._card.tree_right:
                    sections.append(Text(f"  ↩ Queues {len(self._card.tree_right)} tree card(s)", style="green"))
        else:
            sections.append(Text("No card on screen", style="dim italic"))

        sections.append(Rule(style="bright_black"))

        # ── Deque contents ───────────────────────────────────────────────
        all_cards = self._deck.peek_all()
        q_title = Text()
        q_title.append("Weighted Deque", style="bold white")
        q_title.append(f"  ({self._deck.count} cards, cap {self._deck.capacity})", style="dim")
        sections.append(q_title)
        sections.append(Text())

        if not all_cards:
            sections.append(Text("  Deque is empty", style="dim italic"))
        else:
            for idx, c in enumerate(all_cards[:12], 1):
                label, label_style = _SOURCE_LABEL.get(c.source, ("CARD", "dim"))
                row = Text()
                row.append(f"  {idx}.  ", style="bold")
                row.append(f"[{label}]", style=label_style)
                row.append(f"  p={c.priority}  ", style="dim")
                row.append(f"{c.title}\n", style="white")
                sections.append(row)
            if len(all_cards) > 12:
                sections.append(Text(f"  ... and {len(all_cards) - 12} more", style="dim"))

        sections.append(Rule(style="bright_black"))

        # ── Stats snapshot ───────────────────────────────────────────────
        sections.append(Text("Stats snapshot", style="bold white"))
        for stat_id, val in self._state.stats.items():
            icon = self._state.get_stat_icon(stat_id)
            name = self._state.get_stat_name(stat_id)
            bar_w = 20
            filled = round(val / 100 * bar_w)
            color = "green" if 25 <= val <= 75 else ("red" if val < 25 or val > 75 else "yellow")
            bar = Text()
            bar.append(f"  {icon} {name:<12}", style="bold")
            bar.append("█" * filled, style=color)
            bar.append("░" * (bar_w - filled), style="bright_black")
            bar.append(f"  {val}", style=color)
            sections.append(bar)

        # ── Active tags ──────────────────────────────────────────────────
        sections.append(Rule(style="bright_black"))
        sections.append(Text("Active Tags", style="bold white"))
        if self._state.tags:
            for tag_id in sorted(self._state.tags):
                tag_line = Text()
                tag_desc = ""
                for t in self._state.tag_defs:
                    if t.id == tag_id:
                        tag_desc = f"  ({t.description})"
                        break
                tag_line.append(f"  🏷 {tag_id}", style="bold cyan")
                if tag_desc:
                    tag_line.append(tag_desc, style="dim italic")
                sections.append(tag_line)
        else:
            sections.append(Text("  (none)", style="dim italic"))

        # ── Player Profile ───────────────────────────────────────────────
        sections.append(Rule(style="bright_black"))
        sections.append(Text("Player Profile", style="bold white"))
        player = self._state.player
        sections.append(Text(f"  👑 {player.name} — {player.role}", style="bold yellow"))
        if player.traits:
            sections.append(Text(f"     Traits: {', '.join(player.traits)}", style="dim italic"))
        else:
            sections.append(Text("     Traits: (none)", style="dim italic"))
        
        desc_p = player.description if len(player.description) < 60 else player.description[:57] + "..."
        sections.append(Text(f"     {desc_p}", style="dim"))

        # ── NPC Roster ───────────────────────────────────────────────────
        sections.append(Rule(style="bright_black"))
        sections.append(Text("NPC Roster", style="bold white"))
        enabled_npcs = self._state.get_enabled_npcs()
        if not enabled_npcs:
            sections.append(Text("  No NPCs enabled yet.", style="dim italic"))
        else:
            for npc in sorted(enabled_npcs, key=lambda n: n.name):
                sections.append(Text(f"  👤 {npc.name} — {npc.role}", style="bold magenta"))
                if npc.traits:
                    sections.append(Text(f"     Traits: {', '.join(npc.traits)}", style="dim italic"))
                else:
                    sections.append(Text("     Traits: (none)", style="dim italic"))
                
                desc = npc.description if len(npc.description) < 60 else npc.description[:57] + "..."
                sections.append(Text(f"     {desc}", style="dim"))


        # ── Extra state info ─────────────────────────────────────────────
        sections.append(Rule(style="bright_black"))
        meta = Text()
        meta.append(f"Date: {self._state.date_display}  ", style="bold")
        meta.append(f"Turn: {self._state.turn}  ", style="dim")
        meta.append(f"Life: #{self._state.life_number}  ", style="dim")
        season = self._state.current_season()
        if season:
            meta.append(f"Season: {season.icon} {season.name}", style="dim")
        sections.append(meta)

        info = Text()
        info.append(f"Tags: {len(self._state.tags)}  ", style="dim")
        info.append(f"Enabled NPCs: {len(self._state.get_enabled_npcs())}/{len(self._state.npcs)}", style="dim")
        sections.append(info)

        return Group(*sections)
