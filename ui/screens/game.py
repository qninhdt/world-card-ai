from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual import work

from cards.models import Card, ChoiceCard, InfoCard
from ui.widgets.card_view import CardView
from ui.widgets.cost_display import CostDisplay
from ui.widgets.deck_counter import DeckCounter
from ui.widgets.events_panel import EventsPanel
from ui.widgets.stats_bar import StatsBar
from ui.widgets.timeline import Timeline


class GameScreen(Screen):
    BINDINGS = [
        Binding("left", "swipe('left')", "Swipe Left", show=False),
        Binding("a", "swipe('left')", "Swipe Left", show=False),
        Binding("right", "swipe('right')", "Swipe Right", show=False),
        Binding("d", "swipe('right')", "Swipe Right", show=False),
        Binding("m", "show_dag", "Map [M]", show=True),
        Binding("c", "cheat_mode", "Cheat [C]", show=True),
        Binding("q", "quit_game", "Quit", show=True),
    ]

    DEFAULT_CSS = """
    GameScreen {
        layout: vertical;
    }
    #game-header {
        height: auto;
        border-bottom: solid $primary;
    }
    #game-body {
        height: 1fr;
        layout: horizontal;
    }
    #game-body-left {
        width: 1fr;
        align: center middle;
    }
    #game-body-right {
        border-left: solid $primary;
    }
    #bottom-bar {
        height: 3;
        border-top: solid $primary;
        layout: horizontal;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.current_card: Card | None = None
        self._current_story_type: str | None = None
        self._is_current_forced: bool = False

    def compose(self) -> ComposeResult:
        yield StatsBar(id="stats-bar")
        with Horizontal(id="game-body"):
            with Vertical(id="game-body-left"):
                yield CardView(id="card-view")
            yield EventsPanel(id="events-panel")
        with Horizontal(id="bottom-bar"):
            yield Timeline(id="timeline")
            yield DeckCounter(id="deck-counter")
            yield CostDisplay(id="cost-display")

    def on_mount(self) -> None:
        cost_widget = self.query_one("#cost-display", CostDisplay)
        cost_widget.set_tracker(self.app.cost_tracker, demo_mode=getattr(self.app, "demo_mode", False))

        # Start first week
        self._begin_new_week()

    # ── Week Lifecycle ───────────────────────────────────────────────────

    def _begin_new_week(self) -> None:
        """Begin a new week: show season card on first week, fill the deck, draw first card."""
        engine = self.app.engine

        # Start async generation (or demo) immediately; season cards are handled natively


        if getattr(self.app, "demo_mode", False):
            self._fill_week_deck_demo()
            self._draw_next_card()
            self._update_all_widgets()
        else:
            # If we have forced cards (welcome, season transition), draw them first
            if engine.immediate_deque:
                self._draw_next_card()
                self._update_all_widgets()
            else:
                # No forced cards, start async generation immediately
                # Show empty deck state
                self.current_card = None
                self.query_one("#card-view", CardView).set_card(None)
                self._update_deck_counter(is_generating=True)
                self._fill_week_deck()

    # ── Action Handling ─────────────────────────────────────────────────

    def action_swipe(self, direction: str) -> None:
        if not self.current_card:
            return

        engine = self.app.engine
        card = self.current_card

        # Resolve the card
        result = engine.resolve_card(card, direction)

        # Death card flip → resurrect and start new week
        if engine._awaiting_resurrection:
            engine.complete_resurrection()
            self._begin_new_week()
            return

        # Check death
        death = engine.check_death()
        if death:
            engine.handle_death(death)
            # Death card is now in immediate_deque, draw it
            self._draw_next_card()
            self._update_all_widgets()
            return

        # Check ending
        ending = engine.check_ending()
        if ending:
            from ui.screens.ending import EndingScreen
            self.app.switch_screen(EndingScreen(ending))
            return

        # Check if week is over (deck empty)
        if engine.is_week_over:
            # Force UI update so the final card's consequences show BEFORE async wait
            self._update_all_widgets()
            
            # Deck automatically resets — start a new week
            self._begin_new_week()
            return

        self._draw_next_card()
        self._update_all_widgets()

    # ── Card Drawing ────────────────────────────────────────────────────

    def _draw_next_card(self) -> None:
        engine = self.app.engine

        # Detect story type BEFORE drawing
        is_forced = bool(engine.immediate_deque)
        story_type: str | None = None
        if is_forced:
            card_to_draw = engine.immediate_deque[0]
            if engine._awaiting_resurrection:
                story_type = "death"
            elif getattr(card_to_draw, "id", "").startswith("season_"):
                story_type = None  # Normal info card for season transition
            elif engine.state.life_number == 1 and engine.state.turn == 0:
                story_type = "welcome"
            else:
                story_type = "reborn"

        card = engine.draw_card()
        self.current_card = card
        self._is_current_forced = is_forced
        self._current_story_type = story_type if is_forced and card else None

        card_view = self.query_one("#card-view", CardView)
        if card:
            if self._current_story_type:
                card_view.set_story_card(card, self._current_story_type)
            elif isinstance(card, InfoCard):
                card_view.set_info_card(card)
            elif isinstance(card, ChoiceCard):
                card_view.set_card(card)
        else:
            card_view.set_card(None)

        self._update_deck_counter()

    # ── Widget Updates ──────────────────────────────────────────────────

    def _update_all_widgets(self) -> None:
        engine = self.app.engine
        state = engine.state

        # Update seasonal theme
        for i in range(4):
            self.remove_class(f"season-{i}")
        self.add_class(f"season-{state.season_index}")

        self.query_one("#stats-bar", StatsBar).set_stats(state.stats, state.stat_defs)
        self.query_one("#events-panel", EventsPanel).set_events(
            engine.get_all_events_for_display()
        )

        season = state.current_season()
        self.query_one("#timeline", Timeline).set_data(
            day=state.day,
            season_name=season.name if season else "",
            season_icon=season.icon if season else "",
            year=state.year,
            week=state.week_in_season,
            life=state.life_number,
            elapsed_days=state.elapsed_days,
            world_name=state.world_name,
        )
        self._update_deck_counter()

    def _update_deck_counter(self, is_generating: bool = False) -> None:
        engine = self.app.engine
        on_screen = 1 if (self.current_card is not None and not self._is_current_forced) else 0
        self.query_one("#deck-counter", DeckCounter).set_status(
            cur=engine.deque.count + on_screen,
            cap=engine.deque.capacity,
            is_generating=is_generating or engine._is_generating,
        )

    def _update_cost(self) -> None:
        try:
            self.query_one("#cost-display", CostDisplay).update_display()
        except Exception:
            pass

    # ── Deck Filling ────────────────────────────────────────────────────

    @work(group="fill_week")
    async def _fill_week_deck(self) -> None:
        """Generate cards for the entire week deck (async)."""
        engine = self.app.engine
        if engine._is_generating:
            return

        self._update_deck_counter(is_generating=True)
        try:
            success = await engine.fill_week_deck(
                language=getattr(self.app, "language", "en"),
                cost_tracker=self.app.cost_tracker
            )

            self._update_cost()

            if not success:
                # Fallback to demo cards on failure
                self._fill_week_deck_demo()

            # Now draw the first card and update
            self._draw_next_card()
            self._update_all_widgets()
        except Exception:
            import traceback
            traceback.print_exc()
            self._fill_week_deck_demo()
            self._draw_next_card()
            self._update_all_widgets()
        finally:
            self._update_deck_counter(is_generating=False)

    def _fill_week_deck_demo(self) -> None:
        """Fill the deck with demo cards for one week."""
        self.app.engine.fill_week_deck_demo()
        self._update_deck_counter()

    # ── Navigation ──────────────────────────────────────────────────────

    def action_show_dag(self) -> None:
        from ui.screens.dag_view import DAGViewScreen
        self.app.push_screen(DAGViewScreen(self.app.engine.dag))

    def action_cheat_mode(self) -> None:
        from ui.screens.cheat import CheatScreen
        engine = self.app.engine
        self.app.push_screen(
            CheatScreen(
                card=self.current_card,
                deck=engine.deque,
                state=engine.state,
            )
        )

    def action_quit_game(self) -> None:
        self.app.exit()
