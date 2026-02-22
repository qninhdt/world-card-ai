"""Core game engine — orchestrates all backend systems.

``GameEngine`` is the central coordinator.  It owns:
- ``state``          — the ``GlobalBlackboard`` (all mutable game state)
- ``deque``          — the ``WeightedDeque`` of cards for the current week
- ``immediate_deque``— a high-priority queue for story/death/reborn cards
- ``dag``            — the ``MacroDAG`` plot graph
- ``death_loop``     — death detection and resurrection logic
- ``job_queue``      — pending card generation jobs for the Writer agent
- ``events``         — active in-game events

The engine is deliberately free of I/O and UI concerns so it can be tested
directly.  All AI calls and Textual widget updates live in the UI layer.
"""

from __future__ import annotations
import logging
import random
from collections import deque

from typing import TYPE_CHECKING
from uuid import uuid4

from agents.schemas import FunctionCall
from cards.deck import WeightedDeque
from cards.models import Card, CardBase, Choice, ChoiceCard, InfoCard
from cards.resolver import ActionExecutor, ExecuteResult
from cards.validator import (
    PRIORITY_COMMON,
    PRIORITY_EVENT,
    PRIORITY_PLOT,
    PRIORITY_STORY,
    PRIORITY_TREE,
    validate_card_def,
)
from death.loop import DeathInfo, DeathLoop
from game.events import (
    ConditionEvent,
    Event,
    PhaseEvent,
    ProgressEvent,
    TimedEvent,
)
from game.job_queue import CardGenJob, JobQueue
from game.state import (
    DAYS_PER_WEEK,
    DAYS_PER_SEASON,
    GlobalBlackboard,
    NPC,
    Season,
    PlayerCharacter,
    Relationship,
    StatDefinition,
    TagDefinition,
)
from story.dag import MacroDAG, PlotNode

if TYPE_CHECKING:
    from agents.schemas import CardDef, PlotNodeDef, WorldGenSchema

# ── Constants ───────────────────────────────────────────────────────────────
WEEK_DECK_SIZE = DAYS_PER_WEEK  # 7 cards per week

# Structural card ID markers used to route Writer output
_WELCOME_CARD_ID = "welcome_message"
_REBORN_CARD_PREFIX = "reborn_"
_SEASON_CARD_PREFIX = "season_"
_DEATH_CARD_PREFIX = "death_"

logger = logging.getLogger(__name__)


class GameEngine:
    """Central coordinator for all backend game systems.

    Instantiated once per play session.  The UI layer should only call the
    public methods of this class; it must not mutate ``state`` directly.
    """

    def __init__(self) -> None:
        self.state = GlobalBlackboard()
        self.deque = WeightedDeque(capacity=WEEK_DECK_SIZE)
        self.dag = MacroDAG()
        self.death_loop = DeathLoop()
        self.job_queue = JobQueue()
        # Flag set while the Writer async task is running.
        self._is_generating = False
        # High-priority queue for structural cards (welcome, reborn, death, season).
        self.immediate_deque: deque[Card] = deque()
        # Set to True after handle_death(); cleared by complete_resurrection().
        self._awaiting_resurrection: bool = False
        self._first_week_started: bool = False

        # All currently active in-game events.
        self.events: list[Event] = []

    # ── World Building ──────────────────────────────────────────────────

    def build_from_schema(self, world: WorldGenSchema, stat_count: int) -> None:
        """Initialise the engine from a fully generated ``WorldGenSchema``.

        Converts schema definitions into runtime objects, resets the
        ``GlobalBlackboard``, populates the NPC roster, and builds the plot DAG.
        ``stat_count`` controls how many stats are taken from ``world.stats``
        (the schema may contain more than requested).
        """
        stat_defs = [
            StatDefinition(id=s.id, name=s.name, description=s.description, icon=s.icon)
            for s in world.stats[:stat_count]
        ]
        stat_ids = [s.id for s in stat_defs]

        seasons = [
            Season(
                name=p.name,
                description=p.description,
                icon=p.icon,
                on_season_end_calls=p.on_season_end_calls,
                on_week_end_calls=p.on_week_end_calls,
            )
            for p in world.seasons
        ]

        tag_defs = [
            TagDefinition(id=t.id, name=t.name, description=t.description)
            for t in world.tags
        ]

        relationships = [
            Relationship(a=r.a, b=r.b, relationship=r.relationship)
            for r in world.relationships
        ]

        player = PlayerCharacter(
            id="player",
            name=world.player_character.name,
            role=world.player_character.role,
            description=world.player_character.description,
            traits=world.player_character.traits,
        )

        self.state = GlobalBlackboard(
            world_name=world.world_name,
            world_context=world.world_description,
            era=world.era,
            year=world.starting_year,
            start_year=world.starting_year,
            day=1,
            start_day=1,
            season_index=0,
            start_season_index=0,
            player=player,
            stats={sid: 50 for sid in stat_ids},
            stat_defs=stat_defs,
            stat_count=stat_count,
            tag_defs=tag_defs,
            resurrection_mechanic=world.resurrection_mechanic,
            resurrection_flavor=world.resurrection_flavor,
            seasons=seasons,
            relationships=relationships,
        )

        # NPCs
        self.state.npcs = [
            NPC(
                id=n.id,
                name=n.name,
                role=n.role,
                description=n.description,
                traits=n.traits,
                enabled=n.enabled,
            )
            for n in world.npcs
        ]

        # Build DAG
        self._build_dag(world.plot_nodes)

    def _build_dag(self, plot_defs: list[PlotNodeDef]) -> None:
        """Construct the ``MacroDAG`` from ``PlotNodeDef`` objects.

        Nodes are added first, then edges, so forward references in
        ``next_nodes`` are always resolved correctly.  Any reachability
        warnings from the DAG validator are logged at WARNING level.
        """
        self.dag = MacroDAG()
        for pd in plot_defs:
            node = PlotNode(
                id=pd.id,
                plot_description=pd.plot_description,
                condition=pd.condition,
                calls=pd.calls,
                is_ending=pd.is_ending,
                ending_text=pd.ending_text,
            )
            self.dag.add_node(node)

        for pd in plot_defs:
            for next_id in pd.next_nodes:
                self.dag.add_edge(pd.id, next_id)

        warnings = self.dag.validate_reachability()
        for w in warnings:
            logger.warning("[DAG WARNING] %s", w)

    # ── Card Drawing ────────────────────────────────────────────────────

    def draw_card(self) -> Card | None:
        """Draw the next card to show the player.

        ``immediate_deque`` takes priority so structural/story cards (season
        transitions, welcome, death screens) always appear before deck cards.
        """
        if self.immediate_deque:
            return self.immediate_deque.popleft()
        return self.deque.draw()

    # ── Card Resolution ─────────────────────────────────────────────────

    def resolve_card(self, card: Card, direction: str) -> ExecuteResult:
        """Apply a card's action, advance the calendar, and fire lifecycle hooks.

        Returns the ``ExecuteResult`` (stat changes, tree cards, etc.).
        ``InfoCard`` resolutions do not advance the day counter.
        Tree cards are inserted into the deck at high priority so they are
        drawn immediately after the current card.
        """
        executor = ActionExecutor(self.state, self.events)
        result = executor.resolve_card(card, direction)

        # Handle tree cards: insert with high priority so they're drawn next
        if result.tree_cards:
            for tc in result.tree_cards:
                tc.priority = PRIORITY_TREE
                tc.source = "tree"
                self.deque.insert(tc)
            return result

        # ── Action completed (no tree cards) ────────────────────────────
        # Info cards don't consume a day
        if isinstance(card, InfoCard):
            return result

        # Advance 1 day and check boundaries
        crossed = self.state.advance_day()

        # Run day_end hooks for active events
        for event in self.events:
            if hasattr(event, "on_day_end_calls") and event.on_day_end_calls:
                ev_executor = ActionExecutor(self.state, self.events)
                ev_executor.execute(event.on_day_end_calls)

        # Check plot conditions after every day
        self._check_plot_conditions()

        # Week end
        if crossed["week_end"]:
            self._on_week_end()

        # Season end
        if crossed["season_end"]:
            self._on_season_end()

        return result

    # ── Week Lifecycle ──────────────────────────────────────────────────

    @property
    def is_week_over(self) -> bool:
        """A week ends when the deck is empty (all 7 actions consumed)."""
        return self.deque.is_empty and not self.immediate_deque

    def _on_week_end(self) -> None:
        """Called when a week boundary is crossed."""
        season = self.state.current_season()

        # Run season's on_week_end hooks
        if season and season.on_week_end_calls:
            executor = ActionExecutor(self.state, self.events)
            executor.execute(season.on_week_end_calls)

        # Fire pending plot node at week boundary
        self.fire_pending_plot()

        # Check for finished events
        self.check_events()

    def _on_season_end(self) -> None:
        """Called when a season boundary is crossed (every 28 days)."""
        # The season_index was already advanced by advance_day()
        # So get the PREVIOUS season (the one that just ended)
        prev_idx = (self.state.season_index - 1) % len(self.state.seasons) if self.state.seasons else 0
        prev_season = self.state.seasons[prev_idx] if self.state.seasons else None

        # Run previous season's on_season_end hooks
        if prev_season and prev_season.on_season_end_calls:
            executor = ActionExecutor(self.state, self.events)
            executor.execute(prev_season.on_season_end_calls)


    # ── Death ───────────────────────────────────────────────────────────

    def check_death(self) -> DeathInfo | None:
        """Check whether any stat has hit a boundary (0 or 100).

        Returns a ``DeathInfo`` snapshot if the player has died, else ``None``.
        Must be called *after* ``resolve_card`` so stat changes are applied.
        """
        return self.death_loop.check_death(self.state)

    def handle_death(self, death: DeathInfo) -> None:
        """Queue a death info card and set the resurrection flag.

        The death card is pulled from ``state.pending_death_cards`` (pre-generated
        by the Writer each season).  If no pre-generated card exists a simple
        fallback card is created.  Resurrection happens only after the player
        dismisses this card (via ``complete_resurrection()``).
        """
        boundary = "min" if death.cause_value <= 0 else "max"
        key = f"death_{death.cause_stat}_{boundary}"
        death_card = self.state.pending_death_cards.pop(key, None)
        if not death_card:
            # Fallback: create a simple death card
            stat_name = death.cause_stat
            for sd in self.state.stat_defs:
                if sd.id == death.cause_stat:
                    stat_name = sd.name
                    break
            if boundary == "min":
                desc = f"Your {stat_name} has fallen to nothing. The world fades to black..."
            else:
                desc = f"Your {stat_name} has spiraled beyond control. Everything collapses..."
            death_card = InfoCard(
                id=f"death_{uuid4().hex[:8]}",
                title="☠ Death",
                description=desc,
                character="narrator",
                source="info",
                priority=5,
            )
        self.immediate_deque.append(death_card)
        self._awaiting_resurrection = True

    def complete_resurrection(self) -> None:
        """Finalise resurrection after the player dismisses the death card.

        Clears the awaiting flag, runs ``resurrect()``, then skips time to
        the start of the next season so the new life starts fresh.
        """
        self._awaiting_resurrection = False
        karma = self.resurrect()

        # Jump to Day 1 of the next season (time-skip on death is a game rule)
        self.state.advance_to_next_season()
        self.state.is_first_day_after_death = True

    def resurrect(self) -> list[str]:
        """Reset state for a new life while preserving karma tags and DAG endings.

        Clears events, deck, and pending death cards.  Non-ending plot nodes
        are reset so the story can repeat if conditions are met again.
        Returns the list of karma tags carried forward.
        """
        karma = self.death_loop.resurrect(self.state)
        self.events.clear()
        self.deque.clear()
        self.state.pending_death_cards.clear()

        endings_fired = {nid for nid, n in self.dag.nodes.items() if n.is_ending and n.is_fired}
        self.dag.partial_reset(keep_fired=endings_fired)

        return karma

    # ── Plot ────────────────────────────────────────────────────────────

    def _check_plot_conditions(self) -> None:
        """Evaluate all plot node conditions after each action.

        Only the first activatable node is stored.  The actual card generation
        and state mutation are deferred to ``fire_pending_plot()`` at week end
        so the plot card appears at the start of the *next* week.
        """
        nodes = self.dag.get_activatable_nodes(self.state)
        if nodes:
            self.state.pending_plot_node = nodes[0].id

    def fire_pending_plot(self) -> None:
        """Fire the pending plot node (if any) and enqueue a Writer job for its card.

        Called at week end.  The node's ``calls`` are executed immediately
        (e.g. enabling an NPC), but the narrative card is generated async by
        the Writer in the next batch so it appears at the start of the new week.
        """
        node_id = self.state.pending_plot_node
        if not node_id:
            return

        node = self.dag.fire_node(node_id)
        if not node:
            self.state.pending_plot_node = None
            return

        # Execute plot node function calls
        executor = ActionExecutor(self.state, self.events)
        executor.execute(node.calls)

        # Queue Writer job for the plot card (included in next week's deck)
        self.job_queue.enqueue(CardGenJob(
            job_type="plot",
            context={
                "node_id": node.id,
                "plot_description": node.plot_description,
                "is_ending": node.is_ending,
                "ending_text": node.ending_text,
            },
        ))

        self.state.pending_plot_node = None

    def check_ending(self) -> PlotNode | None:
        """Return a fired ending node if one exists, else None."""
        return self.dag.check_ending(self.state)

    # ── Events ──────────────────────────────────────────────────────────

    def check_events(self) -> None:
        """Remove events that have reached their termination condition.

        Called at week end.  Each event type uses a different termination
        check (phase count, progress target, deadline, or a condition expr).
        Condition expressions are evaluated via ``eval()`` with a sandboxed
        namespace — malformed expressions are silently skipped (logged at DEBUG).
        """
        finished_ids = []
        for event in self.events:
            if isinstance(event, PhaseEvent) and event.is_finished:
                finished_ids.append(event.id)
            elif isinstance(event, ProgressEvent) and event.is_finished:
                finished_ids.append(event.id)
            elif isinstance(event, TimedEvent):
                current_date = [self.state.day, self.state.season_index, self.state.year]
                if event.is_expired(current_date):
                    finished_ids.append(event.id)
            elif isinstance(event, ConditionEvent):
                ctx = {
                    "stats": self.state.stats,
                    "tags": self.state.tags,
                    "events": {e.id for e in self.events},
                    "season": self.state.season_index,
                    "day": self.state.day,
                    "year": self.state.year,
                    "elapsed_days": self.state.elapsed_days,
                }
                try:
                    if bool(eval(event.end_condition, {"__builtins__": {}}, ctx)):
                        finished_ids.append(event.id)
                except Exception:
                    logger.debug(
                        "Failed to evaluate end_condition for event '%s': %s",
                        event.id, event.end_condition, exc_info=True
                    )

        self.events = [e for e in self.events if e.id not in finished_ids]

    def get_all_events_for_display(self) -> list[dict]:
        """Serialise active events into plain dicts suitable for the UI.

        Each dict contains at minimum: ``type``, ``name``, ``icon``,
        ``description``.  Events that have a ``progress_display`` property
        also include a ``progress`` key.
        """
        events_display = []
        for e in self.events:
            display = {
                "type": e.type if hasattr(e, "type") else "unknown",
                "name": e.name,
                "icon": e.icon,
                "description": e.description,
            }
            if hasattr(e, "progress_display"):
                display["progress"] = e.progress_display
            events_display.append(display)
        return events_display

    # ── Generation ──────────────────────────────────────────────────────

    def get_week_deck_size(self) -> int:
        """Return the number of cards that should fill one week's deck."""
        return WEEK_DECK_SIZE

    def get_generation_context(self) -> dict:
        """Build the context dict passed to the Writer for batch generation.

        Includes the current state snapshot, DAG context, active events, and
        season info.  ``is_season_start`` is True on Day 1 of any season so
        the Writer knows to generate structural cards (welcome, season, death).
        """
        season = self.state.current_season()
        return {
            "is_season_start": self.state.day == 1,
            "is_first_day_after_death": self.state.is_first_day_after_death,
            "snapshot": self.state.snapshot(),
            "dag_context": self.dag.get_writer_context(self.state),
            "ongoing_events": self.get_all_events_for_display(),
            "available_tags": [
                {"id": t.id, "name": t.name, "description": t.description}
                for t in self.state.tag_defs
            ],
            "season": {
                "name": season.name if season else "",
                "description": season.description if season else "",
                "week": self.state.week_in_season,
            },
        }

    def get_common_count(self) -> int:
        """How many common cards to generate (deck size minus special jobs)."""
        job_count = self.job_queue.count
        return max(1, WEEK_DECK_SIZE - job_count)

    def add_cards_from_defs(self, card_defs: list[CardDef]) -> int:
        """Validate and insert cards from Writer output."""
        cards = []
        for cd in card_defs:
            card = validate_card_def(cd, self.state)
            cards.append(card)
        return self.deque.bulk_insert(cards)

    def process_batch_output(self, batch_output, is_season_start: bool) -> None:
        """Route Writer batch output to the correct destinations.

        Structural cards (welcome, reborn, season, death) are stored on state
        for later injection into ``immediate_deque``.  All other cards go
        directly into the week deck.
        """
        from agents.schemas import InfoCardDef

        deck_cards = []
        for cd in batch_output.cards:
            card_id = getattr(cd, "id", "") or ""

            if isinstance(cd, InfoCardDef) and is_season_start:
                if card_id == _WELCOME_CARD_ID:
                    self.state.welcome_card = validate_card_def(cd, self.state)
                    continue
                if card_id.startswith(_REBORN_CARD_PREFIX):
                    self.state.reborn_card = validate_card_def(cd, self.state)
                    continue
                if card_id.startswith(_SEASON_CARD_PREFIX):
                    self.state.season_start_card = validate_card_def(cd, self.state)
                    continue
                if card_id.startswith(_DEATH_CARD_PREFIX):
                    self.state.pending_death_cards[card_id] = validate_card_def(cd, self.state)
                    continue

            deck_cards.append(cd)

        self.add_cards_from_defs(deck_cards)

        if is_season_start:
            # Insert season card first, then reborn/welcome so welcome/reborn
            # remains at index 0 of the immediate_deque.
            if self.state.season_start_card:
                self.immediate_deque.appendleft(self.state.season_start_card)
                self.state.season_start_card = None

            if self.state.reborn_card:
                self.immediate_deque.appendleft(self.state.reborn_card)
                self.state.reborn_card = None

            if self.state.welcome_card:
                self.immediate_deque.appendleft(self.state.welcome_card)
                self.state.welcome_card = None

            self.state.is_first_day_after_death = False

    def prepare_demo_week(self) -> None:
        """Populate the deck with demo/offline cards for the current week.

        Called instead of the async Writer path when running in demo mode.
        All card-creation and state-mutation logic lives here so the UI layer
        only needs to call this method and then refresh its widgets.
        """
        from game.demo import get_demo_card_pool
        from cards.models import Choice, ChoiceCard, InfoCard

        if self.state.day == 1:
            # ── Death cards for every stat boundary ──────────────────────
            for sd in self.state.stat_defs:
                for bound in ("min", "max"):
                    self.state.pending_death_cards[f"death_{sd.id}_{bound}"] = InfoCard(
                        id=f"demo_death_{sd.id}_{bound}",
                        title="☠ Death",
                        description=(
                            f"Your {sd.name} reached its "
                            f"{'minimum' if bound == 'min' else 'maximum'} limit."
                        ),
                        character="narrator",
                        source="info",
                        priority=5,
                    )

            # ── Welcome / reborn card ────────────────────────────────────
            if self.state.elapsed_days == 1 and self.state.life_number == 1:
                self.immediate_deque.append(InfoCard(
                    id="demo_welcome",
                    title="A Kingdom Awaits",
                    description="Welcome to the demo world. Your reign begins now.",
                    character="narrator",
                    source="info",
                    priority=5,
                ))
            elif self.state.is_first_day_after_death:
                self.immediate_deque.append(InfoCard(
                    id="demo_reborn",
                    title="Awakening",
                    description=f"Life #{self.state.life_number}. The cycle begins anew.",
                    character="narrator",
                    source="info",
                    priority=5,
                ))
                self.state.is_first_day_after_death = False

            # ── Season transition card ───────────────────────────────────
            season = self.state.current_season()
            if season:
                self.immediate_deque.append(InfoCard(
                    id=f"demo_season_{self.state.year}_{self.state.season_index}",
                    title=f"{season.icon} {season.name}",
                    description=season.description,
                    character="narrator",
                    source="info",
                    priority=5,
                ))

        # ── Process pending jobs (plot nodes only in demo) ───────────────
        jobs = self.job_queue.drain()
        for job in jobs:
            if job.job_type == "plot":
                desc = job.context.get("plot_description", "A major event occurs.")
                if job.context.get("is_ending"):
                    desc += "\n\n" + job.context.get("ending_text", "")
                plot_card = ChoiceCard(
                    id=f"demo_plot_{job.context.get('node_id')}",
                    title="Story Event",
                    description=desc,
                    character="narrator",
                    source="plot",
                    priority=4,
                    left=Choice(text="Continue", calls=[]),
                    right=Choice(text="Continue", calls=[]),
                )
                self.deque.insert(plot_card)

        # ── Fill deck from demo pool ─────────────────────────────────────
        pool = get_demo_card_pool()
        random.shuffle(pool)
        self.deque.bulk_insert(pool[: self.get_week_deck_size()])
