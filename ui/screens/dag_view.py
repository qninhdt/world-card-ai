"""Fullscreen DAG visualization screen — press M during gameplay."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from story.dag import MacroDAG


class DAGViewScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("m", "dismiss", "Close"),
    ]

    DEFAULT_CSS = """
    DAGViewScreen {
        align: center middle;
    }
    #dag-container {
        width: 70;
        height: 80%;
        border: heavy $accent;
        background: $surface;
        padding: 1 2;
    }
    #dag-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        height: auto;
        margin-bottom: 1;
    }
    #dag-legend {
        height: auto;
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    #dag-scroll {
        height: 1fr;
    }
    #dag-content {
        height: auto;
    }
    """

    def __init__(self, dag: MacroDAG, **kwargs) -> None:
        super().__init__(**kwargs)
        self.dag = dag

    def compose(self) -> ComposeResult:
        with Vertical(id="dag-container"):
            yield Static("◆  STORY MAP  ◆", id="dag-title")
            yield Static(
                "[green]✓[/] Fired  [yellow]◆[/] Available  [dim]○[/] Locked  [bold]★[/] Ending",
                id="dag-legend",
            )
            with VerticalScroll(id="dag-scroll"):
                yield Static(id="dag-content")

    def on_mount(self) -> None:
        self._render_dag()

    def _render_dag(self) -> None:
        visual = self.dag.get_visual_graph()
        nodes = visual["nodes"]
        edges = visual["edges"]

        lines: list[str] = []

        # Find root nodes (no predecessors)
        all_ids = set(nodes.keys())
        children = {to_id for _, to_id in edges}
        roots = all_ids - children

        # BFS to render in layers
        visited = set()
        queue = list(roots) if roots else list(all_ids)[:1]
        layer = 0

        while queue:
            next_queue = []
            if layer > 0:
                lines.append("")
                lines.append("  │")

            for node_id in queue:
                if node_id in visited:
                    continue
                visited.add(node_id)

                info = nodes[node_id]
                status = info["status"]
                is_ending = info["is_ending"]

                # Status icon
                if is_ending:
                    icon = "★"
                    if status == "fired":
                        icon_line = f"[green]★ {node_id}[/] [dim](ending - reached)[/]"
                    elif status == "activatable":
                        icon_line = f"[yellow]★ {node_id}[/] [bold](ending - available)[/]"
                    else:
                        icon_line = f"[dim]★ {node_id}[/] [dim](ending - locked)[/]"
                elif status == "fired":
                    icon_line = f"[green]✓ {node_id}[/]"
                elif status == "activatable":
                    icon_line = f"[yellow]◆ {node_id}[/]"
                else:
                    icon_line = f"[dim]○ {node_id}[/]"

                lines.append(f"  {icon_line}")

                # Description (truncated)
                desc = info["description"][:80]
                lines.append(f"    [dim]{desc}...[/]" if len(info["description"]) > 80 else f"    [dim]{desc}[/]")

                # Conditions
                cond = info.get("condition")
                if cond:
                    lines.append(f"    [italic dim]Requires: {cond}[/]")

                # Successors
                for succ in info.get("successors", []):
                    if succ not in visited and succ not in next_queue:
                        next_queue.append(succ)

            queue = next_queue
            layer += 1

        # Render any unvisited nodes
        for node_id in all_ids - visited:
            info = nodes[node_id]
            lines.append(f"\n  [dim]○ {node_id}[/]")
            lines.append(f"    [dim]{info['description'][:60]}...[/]")

        content = "\n".join(lines)
        self.query_one("#dag-content", Static).update(content)
