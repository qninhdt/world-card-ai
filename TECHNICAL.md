# Game System

## Queues
- Deck queue:
  - A queue of cards to be drawn.
  - Reset at the beginning of each week.
- Immediate queue:
  - Stores cards that must be shown immediately.
  - e.g.: welcome/death/reborn/season cards.
  - Derived cards are also added to this queue (tree cards, ...) via `add_card` function.

## Event
- Event is a scheduled task.
- There are 3 types of events:
  - Phase Event: This event progresses through a series of phases.
    - e.g.: "The Siege of the Castle" has 3 phases: "The Siege Begins", "The Siege Continues", "The Siege Ends".
  - Progress Event: This event tracks a progress towards a goal.
    - e.g.: "Collect 100 gold" has a progress of 0/100.
  - Timed Event: This event expires at a specific time.
    - e.g.: "The Siege of the Castle" expires on 10/10/1030.

## Game Loop

```python
class DeathException(Exception):
    """Custom exception to interrupt the game loop upon death."""
    def __init__(self, reason: str):
        self.reason = reason

class EndGameException(Exception):
    """Custom exception to completely stop the game loop upon winning."""
    pass

class RestartGameException(Exception):
    """Custom exception to reset the game but keep the story tree progression."""
    pass

def enforce_state_checks():
    """
    Centralized function to validate stats, resolve finished events, 
    and evaluate story nodes.
    Raises DeathException if lethal thresholds are met.
    """
    global pending_story_node, ongoing_events

    # 1. Check Death immediately
    for stat_name, value in stats.items():
        if value <= 0:
            raise DeathException(f"{stat_name}_<=0")
        if value >= 100:
            raise DeathException(f"{stat_name}_>=100")

    # 2. Check and exit finished events safely
    for event in list(ongoing_events):
        if not event.is_finished and event.check_finished():
            event.is_finished = True
            event.on_exit()
            
            # Re-check death in case on_exit killed the player
            for stat_name, value in stats.items():
                if value <= 0:
                    raise DeathException(f"{stat_name}_<=0")
                if value >= 100:
                    raise DeathException(f"{stat_name}_>=100")

    # 3. Check story nodes (only if no pending transition exists)
    if not pending_story_node:
        for node in story_tree.nodes[story_tree.active_nodes[-1]]:
            if node.condition():
                pending_story_node = node
                break

async def generate_cards():
    if story_node.is_ending:
        cards, _ = await llm.generate_cards([ending_card_request()], [])

        # next weeks have only one cards
        game.set_cards(cards)

        return

    info_card_requests = []
    
    # generate new content for next weeks
    while len(card_requests) < DECK_SIZE:
        # fill the deck with basic cards
        card_requests.append(random_basic_card_request())
    
    # extend card_requests with info cards for welcome/reborn/season/death
    if is_first_day_of_life():
        if life_count == 1:
            info_card_requests.append(welcome_card_request())
        else:
            info_card_requests.append(reborn_card_request())

    if is_first_day_of_season():
        info_card_requests.append(season_card_request())

    for stat in stats:
        info_card_requests.append(death_card_request(stat, "<=0"))
        info_card_requests.append(death_card_request(stat, ">=100"))

    cards, info_cards = await llm.generate_cards(card_requests, info_card_requests)
    game.set_cards(cards)
    game.set_info_cards(info_cards)

    card_requests = []

async def update_game_progress():
    global story_node, pending_story_node

    if story_node.is_ending:
        story_node.on_enter()
        return

    # add current story node to the parent story nodes
    game.add_parent_story_node(story_node)

    # update current story node
    story_node = pending_story_node
    pending_story_node = None

    game.story_score += story_node.story_effect_score

    if game.story_score >= 100:
        # end the story with a certain probability (0.5)
        is_ending = True if random.random() < 0.5 else False
    else:
        is_ending = False

    # generate new child story nodes
    child_nodes = await llm.generate_story_node(story_node, is_ending=is_ending)
    game.add_story_nodes(child_nodes)

    # callback
    story_node.on_enter()

async def game_loop() -> Card:
    global life_count, date, stats, ongoing_events, card_requests, pending_story_node
    
    life_count = 1
    date = GameDate(day=1, season=1, year=1030)

    try:
        while True:
            try:
                async for card in life_loop():
                    yield card

                # reset state except tags
                stats = {k: 50 for k in stats}        
                ongoing_events = []
                card_requests = []
                immediate_cards = []
                pending_story_node = None

                # skip to next season
                date.advance_to_next_season()
                life_count += 1
            
            except RestartGameException:
                # Reset everything EXCEPT current story tree to encourage exploring other nodes and endings

                life_count = 1
                date = GameDate(day=1, season=1, year=1030)
                stats = {k: 50 for k in stats}
                ongoing_events = []
                card_requests = []
                immediate_cards.queue = []
                pending_story_node = None
                game.story_score = 0

                continue

    except EndGameException:
        return

async def life_loop() -> Card:
    global ongoing_events

    await generate_cards()

    if life_count == 1:
        yield game.info_cards["welcome"]
    else:
        yield game.info_cards["reborn"]

    try:
        while True: # year
            for season_idx in range(date.season, 5): # seasons: 1 to 4
                current_season = world.seasons[season_idx - 1]
                yield game.info_cards["season"]

                for week in range(1, 5): # weeks: 4
                    for day in range(1, 8): # days: 7
                        
                        # internal navigation between cards in the same day
                        flag = True
                        while flag: 
                            card = game.deck.get_current_card()
                            swipe_result = await wait_for_player_swipe(card)
                            
                            enforce_state_checks()
                            flag = swipe_result.has_internal_navigation()

                        # CHECK ENDING
                        if story_node.is_ending:
                            if game.player_choosed_restart:
                                raise RestartGameException()
                            else:
                                raise EndGameException()

                        # --- DAY END ---
                        for event in list(ongoing_events):
                            if not event.is_finished:
                                event.on_day_end()
                                
                        current_season.on_day_end()
                        story_node.on_day_end()

                        enforce_state_checks()

                        # --- WEEK END ---
                        if date.is_last_day_of_week():
                            
                            # remove finished events completely
                            ongoing_events = [e for e in ongoing_events if not e.is_finished]

                            for event in list(ongoing_events):
                                event.on_week_end()
                                
                            current_season.on_week_end()
                            story_node.on_week_end()

                            enforce_state_checks()

                            # --- SEASON END ---
                            if date.is_last_day_of_season():
                                for event in list(ongoing_events):
                                    if not event.is_finished:
                                        event.on_season_end()
                                    
                                current_season.on_season_end()
                                story_node.on_season_end()
                                
                                enforce_state_checks()

                            # switch to the pending story 
                            if pending_story_node:
                                await update_game_progress()
                                enforce_state_checks()

                        date.advance_to_next_day()
                    
                    await generate_cards()

    except DeathException as e:
        yield game.info_cards[e.reason]
        return
```

# Scheme

```python
class Scriptable:
    scripts: dict[str, str] # stores source code of the functions

    on_enter: Optional[str] # function name to be called when the card is entered or started.
    on_exit: Optional[str] # function name to be called when the card is exited or finished.
    on_day_end: Optional[str] # function name to be called at the end of a day.
    on_week_end: Optional[str] # function name to be called at the end of a week.
    on_season_end: Optional[str] # function name to be called at the end of a season.
    on_swipe_right: Optional[str] # function name to be called when the card is swiped right.
    on_swipe_left: Optional[str] # function name to be called when the card is swiped left.

class Object:
    id: str
    name: str
    icon: str
    description: str

    def to_string(self) -> str:
        """Get the string representation of the component. Used in the prompt."""

class Stat(Object):
    pass

class Component(Object, Scriptable):
    pass

class GameDate:
    day: int # 1 -> 28
    season: int # 1 -> 4
    year: int # any positive integer

    def to_string(self) -> str:
        """Get the string representation of the game date. Used in the prompt."""

class Card(Component):
    # type of the card
    # 
    # welcome: The first message sent to the player after the game starts.
    # death: The message sent to the player when they die.
    # reborn: The message sent to the player when they are reborn.
    # season: The message sent to the player at the start of a season.
    # basic: A single choice card.
    # tree: A decision tree card.
    # event: A card that can fire an event.
    # advanced: A card with a complicated logic.
    #
    # welcome, death, reborn, season are info cards. They don't have choices.
    kind: Literal["welcome", "death", "reborn", "season", "basic", "tree", "event", "advanced"]

    npc_id: Optional[str]
    left_text: Optional[str]
    right_text: Optional[str]

class CardRequest:
    npc_id: str
    prompt: str

class Event(Component):
    kind: str

    # phase
    phases: Optional[list[str]]
    current_phase: Optional[int]

    # progress
    target: Optional[int]
    current: Optional[int]
    progress_label: Optional[str]

    # time
    deadline: Optional[int]

class Day:

    # day cannot create a new npc
    related_cards: dict[str, Card]
    related_events: Optional[dict[str, Event]]

    current_card: str

class StoryNode(Component):
    story_effect_score: int

    # story node cannot create cards immediately. It can only request cards to be added to the deck in the next week.
    related_events: Optional[dict[str, Event]]
    related_npcs: Optional[dict[str, NPC]]

class StoryTree:
    # nodes[i] is the list of story nodes that are at the same level i
    # level 0 has only one node: the root node.
    # level 1 has N_1 nodes connected to the root node.
    # level 2 has N_2 nodes connected to the active nodes in level 1.
    # ...
    # level L has N_L nodes connected to the active nodes in level L-1.
    nodes: list[list[StoryNode]]

    # indices of the active nodes in the nodes list
    # active_nodes[0] is always 0 (root node).
    active_nodes: list[int]

    def to_string(self) -> str:
        """Get the string representation of the story tree. 

        Includes:
        - Current node
        - All parent nodes of current node
        - All children nodes of current node
        - Ignore nodes that are not active
        """

class Entity(Component):
    born_year: int
    traits: list[str]
    role: str

class NPC(Entity):
    is_enabled: bool

class Player(Entity):
    stats: dict[str, int]
    tags: list[str]

class Season(Component):
    pass

class World:
    name: str
    description: str
    era: str
    starting_year: int
    seasons: list[Season]

class CardDeck:
    """
    Main deck is reset at the beginning of each week.
    Requested cards are distributed to next weeks.
    Minimum number of basic cards per week is DECK_SIZE // 2.

    """
    
    days: list[Day]
    immediate_cards: queue[Card]
    card_requests: queue[CardRequest]

    current_day_idx: int # 0-based index

    # card history with window size CARD_HISTORY_WINDOW
    swiped_cards: deque[Card] # cards that have been swiped left or right

    # start cards
    welcome_card: Optional[Card] # null for 2nd and later lifes
    reborn_card: Optional[Card] # null for first life

    # stat_index -> [death card for stat = 0, death card for stat = 100]
    death_cards: list[list[Card]]

    # season start card
    season_card: Card

class GameContext:
    player: Player
    world: World
    npcs: dict[str, NPC]
    events: dict[str, Event]
    story_tree: StoryTree
    deck: CardDeck
```

# Starlark Engine

## Script Context
```python
# state
stats: Dict[str, int] # e.g., {"strength": 10, "intelligence": 8, "charisma": 6}
tags: List[str] # e.g., ["brave", "cunning", "loyal"]

# builtin functions
def random() -> float:
    """Return a random float in the range [0.0, 1.0)."""

# functions
def update_stats(stat_changes: Dict[str, int]) -> None:
    """Update the player's stats based on the provided changes."""

def add_tags(new_tags: List[str]) -> None:
    """Add new tags to the player's profile."""

def remove_tags(tags_to_remove: List[str]) -> None:
    """Remove specified tags from the player's profile."""

def add_npc(npc_id: str, name: str, description: str, role: str, born_year: int, traits: List[str], enabled: bool) -> None:
    """Add a new NPC to the world. Set enabled to True if the NPC should be active immediately, or False if it should be added but not active until enabled."""

def enable_npc(npc_id: str) -> None:
    """Enable an NPC to be active in the story."""

def disable_npc(npc_id: str) -> None:
    """Disable an NPC from being active in the story."""

def add_event(event_id: str) -> None:
    """Add a new event to the world."""

def add_card(npc_id: str) -> None:
    """Show this card to the player immediately."""

def request_card(npc_id: str, prompt: str) -> None:
    """
    Request a new card from the AI to be added to the deck in the next week's draw pile, associated with the specified NPC.
    
    prompt: A prompt for the AI to generate a card.

    - Used when an event is finished or as a consequence of a choice in the next week.
    """
```

## Available Hooks

```python

def condition() -> bool:
    """Define a condition that must be met for a story node"""

def on_swipe_right() -> None:
    """Define what happens when the card is swiped right."""

def on_swipe_left() -> None:
    """Define what happens when the card is swiped left."""

def on_enter() -> None:
    """Define what happens when the story node/card/event is entered or started."""

def on_exit() -> None:
    """Define what happens when the story node/card/event is exited or finished."""

def on_day_end() -> None:
    """Define what happens at the end of a day."""

def on_week_end() -> None:
    """Define what happens at the end of a week."""

def on_season_end() -> None:
    """Define what happens at the end of a season."""
```

## Code Examples

```python
# simple stat/tag updates or NPC additions:
update_stats({"strength": +1})
add_tags(["brave"])
add_npc("guard_1", "Guard", "A loyal guard of the kingdom.", "guard", 1030, ["loyal", "strong"], True)

# kill an NPC then spawn a new one to replace it:
disable_npc("guard_1")
add_npc("guard_2", "Guard", "A loyal guard of the kingdom, resurrected after the death of the previous guard.", "guard", 1031, ["loyal", "strong"], True)

# the King ordered the explorer to seek treasures across the sea.
def on_finish():
    roll = random()
    if roll < 0.7:
        add_card("explorer", "The Explorer returns triumphant with treasures from the sea expedition, increasing your wealth and reputation.")
    else:
        add_card("explorer", "The Explorer returns empty-handed from the sea expedition, decreasing your morale and resources.")

def on_swipe_right(): # or on_enter
    disable_npc("explorer")
    add_event(
        id="sea_expedition",
        name="Sea Expedition",
        description="The Explorer has set sail to seek treasures across the sea.",
        deadline="12-2-1030",
        effects="When the expedition returns, if it is successful, increase player's wealth and reputation. If it fails, decrease player's morale and resources."
        on_finish="@on_finish"
    )

# for consequences that happen immediately in the next week, call add_card directly
# trigger card: The Queen: "Tresures from the Sea is just a myth?"
# Option: Call the Explorer back!
stop_event("sea_expedition")
enable_npc("explorer")
add_card("explorer", "The Explorer returns immediately from the sea expedition, claiming that he couldn't find any treasures. Your morale and resources take a hit.")

# trigger card prompt: The Explorer returns immediately from the sea expedition, claiming that he couldn't find any treasures. Your morale and resources take a hit.
# trigger card description: The Explorer: "As commanded, the fleet has returned. But do not mourn the interrupted journey, Sire. We found nothing out there but salt and false myths."
# Option: "You are such a failure! Get out of my sight!"
update_stats(morale=-2)

# the King ordered the assassin to kill the explorer while the explorer is on the sea expedition.
stop_event("sea_expedition")
disable_npc("explorer")
```

# Prompt Engineering

- Contains only AI-generated fields.
- All id must be unique English strings with snake_case formatting.

## Game History

```
The Merchant: I have same goods for sale, but I also have a special item that might interest you.
Player: Get out!

---

Queen: You have been a loyal servant to the kingdom for many years. I have a special task for you. Will you accept it?
Player: What is the task?
Queen: There is a dangerous beast terrorizing the countryside. I need you to defeat it and bring me its head as proof. Will you do this for me?
Player: I will do it

---


```

## World

### Input
```yaml
theme: string # e.g., "medieval fantasy", "post-apocalyptic", "sci-fi space opera", etc.
```

<output>

# World Core
```yaml
id: string
name: string
description: string
starting_year: int    
```

# Stats
```yaml
stats[N]{id,name,icon,description}:
    string,string,string,string
```

# Seasons
```yaml
seasons[4]{id,name,icon,description}:
    int,string,string,string
```

# Player and NPCs
```yaml
player:
    name: string
    description: string
    role: string
    born_year: int
    traits: string|string|...

npcs[N]{id,name,icon,description,role,born_year,traits}:
    string,string,string,string,string,int,string|string|...

relationships[M]{npc1_id,npc2_id,description}: # use "player" as id for player character
    string,string,string

```
</output>

## Story Node

### Input

```yaml
world:
    <same as above>

    npcs[N]{id,name,description,role,born_year,traits}: # all enabled NPCs (included newly added ones)
        string,string,string,string,int,string|string|...

ongoing_events[N]{id,name,description,effects}:
    string,string,string,effect|effect|...

parent_story_nodes[N]{id,description}: # parent story nodes that have been fired
    string,string

current_story_node:
    id: string
    description: string

    # starlark expression that evaluates to true or false
    # e.g., "stats['strength'] > 5 and 'brave' in tags" or "npc['guard']['loyalty'] < 3"
    # e.g., "player['traits'].contains('brave') and player['stats']['strength'] > 5"
    conditions: string

    # how this story node affects the progress towards the ending (-10 to +10)
    # >0 mean this node makes the ending more likely to fire 
    # <0 means this node makes the ending less likely to fire
    story_effect_score: int
```

### Output

```yaml
story_node:

    child_nodes[N]{id,description,conditions,story_effect_score}:
        string,string,string,int
        

```

## Cards
- Writer LLM has to generate 7 groups of cards and events for 7 days.
- Each group contains all related cards and events
- Entry card of a day is the first card of group by default.
- Cards and events are definied by a yaml code (metadata) and a python code (script, optional)
- Basic card should have only one card.
- Event card should have one or more events.
- Tree cards should have mutiple cards for navigation.
- Cycle is allowed, e.g. player can navigate to the same card multiple times.
- Each group must start with a 1-level heading with group index.

<output>

# 1

## card_<card_id>

```yaml
name: str
description: str
...
```
```python
def on_swipe_right():
    update_stats(...)
    add_event("event_<event_id>")

def on_swipe_left():
    update_stats(...)
```
## event_<event_id>

```yaml 
name: str
description: str
phases: str[]
```
```python
def on_exit():
    request_card("the_explorer", "The explorer returns with a huge treasure chest.")
    enable_npc("the_explorer")
```

# 2

.
.
.

# 7
```yaml

```
```python

```
</output>
