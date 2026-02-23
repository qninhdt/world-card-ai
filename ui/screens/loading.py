"""Loading screen — shown while the Architect generates the world and the
Writer produces the first batch of cards.

Two paths:
  **Demo mode** — loads the pre-built ``get_demo_world()`` synchronously with
  simulated progress steps (no API calls needed).

  **AI mode** — streams the Architect output section by section, updating the
  progress list as each JSON block arrives.  Once the world is built the Writer
  generates the initial card batch, with routing delegated to
  ``engine.process_batch_output()``.

On completion both paths switch to ``GameScreen``.
"""

from __future__ import annotations

import random

from textual.app import ComposeResult
from textual.containers import Center, Middle, Vertical
from textual.screen import Screen
from textual.widgets import Label, ProgressBar, Static
from textual.worker import Worker, WorkerState


# Step labels for the progress display (fallback if AI title not yet received)
STEP_PLACEHOLDERS = [
    "World Core...",
    "Stats...",
    "NPCs...",
    "Story...",
    "Seasons...",
    "First Cards...",
]


class LoadingScreen(Screen):
    DEFAULT_CSS = """
    LoadingScreen {
        align: center middle;
    }
    #loading-box {
        width: 56;
        height: auto;
        padding: 2 3;
        border: heavy $accent;
        background: $surface;
    }
    #loading-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #steps-list {
        height: auto;
        margin-bottom: 1;
    }
    .step-label {
        height: 1;
    }
    #progress-bar {
        margin-top: 1;
        margin-bottom: 1;
    }
    #loading-cost {
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._step_titles: list[str] = list(STEP_PLACEHOLDERS)
        self._completed: int = 0
        self._total_steps: int = len(STEP_PLACEHOLDERS)

    def compose(self) -> ComposeResult:
        with Center():
            with Middle():
                with Vertical(id="loading-box"):
                    yield Static("◆  Building Your World  ◆", id="loading-title")
                    yield Vertical(id="steps-list")
                    yield ProgressBar(
                        total=self._total_steps,
                        show_eta=False,
                        id="progress-bar",
                    )
                    yield Static("", id="loading-cost")

    def on_mount(self) -> None:
        self._render_steps()
        self._generate()

    def _render_steps(self) -> None:
        """Render the step list with ✓/●/○ markers."""
        container = self.query_one("#steps-list", Vertical)
        container.remove_children()
        for i, title in enumerate(self._step_titles):
            if i < self._completed:
                marker = "[green]✓[/]"
                style = "dim"
            elif i == self._completed:
                marker = "[yellow]●[/]"
                style = "bold"
            else:
                marker = "[dim]○[/]"
                style = "dim"
            label = Label(f"  {marker}  {title}", classes="step-label")
            label.styles.text_style = style if style != "dim" else "none"
            if style == "dim":
                label.styles.color = "grey"
            container.mount(label)

    def _advance_step(self, title: str | None = None) -> None:
        """Mark current step as completed and optionally update next step's title."""
        if title and self._completed < len(self._step_titles):
            self._step_titles[self._completed] = title
        self._completed += 1
        self._render_steps()
        self.query_one("#progress-bar", ProgressBar).advance(1)

    def _generate(self) -> None:
        self.run_worker(self._do_generate(), exclusive=True)

    @property
    def _is_demo(self) -> bool:
        return getattr(self.app, "demo_mode", False)

    async def _do_generate(self) -> None:
        app = self.app
        engine = app.engine

        if self._is_demo:
            # Fast path: load demo world with simulated progress
            from game.demo import get_demo_world, get_demo_card_pool

            self._step_titles = [
                "Loading the Kingdom of Ardenvale...",
                "Summoning knights and nobles...",
                "Dealing the first hand...",
            ]
            self._total_steps = 3
            self.query_one("#progress-bar", ProgressBar).update(total=3)
            self._completed = 0
            self._render_steps()

            world = get_demo_world()
            self._advance_step()

            engine.build_from_schema(world, app.stat_count)
            self._advance_step()

            pool = get_demo_card_pool()
            random.shuffle(pool)
            engine.deque.bulk_insert(pool[:engine.deque.capacity])
            self._advance_step()

        else:
            # Streaming path: single LLM call with progressive section parsing
            from agents.architect import StreamSection, stream_world
            from agents.schemas import WorldGenSchema

            world: WorldGenSchema | None = None

            async for item in stream_world(
                theme=app.theme_choice,
                stat_count=app.stat_count,
                language=getattr(app, "language", "en"),
                cost_tracker=app.cost_tracker,
            ):
                if isinstance(item, StreamSection):
                    # A section completed — update step title and advance
                    self._advance_step(title=item.title)

                    cost_text = f"Cost: {app.cost_tracker.summary}"
                    self.query_one("#loading-cost").update(cost_text)
                elif isinstance(item, WorldGenSchema):
                    world = item

            if world is None:
                self.query_one("#loading-cost").update("Error: failed to generate world")
                return

            engine.build_from_schema(world, app.stat_count)


            # Step 7: Generate first Writer batch
            self._advance_step(title="Dealing the first hand...")

            from agents.writer import Writer

            writer = Writer(
                world_context=engine.state.world_context,
                stat_names=[sd.id for sd in engine.state.stat_defs],
                cost_tracker=app.cost_tracker,
                language=getattr(app, "language", "en"),
            )

            common_count = engine.deque.capacity
            jobs = engine.job_queue.drain()
            context = engine.get_generation_context()
            is_season_start = context.get("is_season_start", False)

            batch_output = await writer.generate_batch(common_count, jobs, context)

            # Route structural cards (welcome, season, death) to their state
            # slots and insert the rest into the deck — same logic as game.py.
            engine.process_batch_output(batch_output, is_season_start)

            cost_text = f"Total: {app.cost_tracker.summary}"
            self.query_one("#loading-cost").update(cost_text)

        # Done — switch to game
        from ui.screens.game import GameScreen

        self.app.switch_screen(GameScreen())
