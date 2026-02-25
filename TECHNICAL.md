# Game System

## Deck Queue


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

def add_event(event_id: str, name: str, description: str) -> None:
    """Add a new ongoing event to the world."""

def add_card(npc_id: str, title: str, description: str) -> None:
    """Add a new card to the deck in the next week's draw pile, associated with the specified NPC."""
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

### Output

```yaml
world:
    id: string
    name: string
    description: string
    starting_year: int

    # Seasons
    seasons[4]{id,name,icon,description}:
        int,string,string

    # Player and NPCs
    player:
        name: string
        description: string
        role: string
        born_year: int
        traits: string|string|...
        resurrection_mechanic: string # The spirit of the fallen king shall be passed down to the successor child.

    npcs[N]{id,name,description,role,born_year,traits}:
        string,string,string,string,int,string|string|...

    relationships[M]{npc1_id,npc2_id,description}: # use "player" as id for player character
        string,string,string
```

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
    plot_effect_score: int
```

### Output

```yaml
story_node:

    

    child_nodes[N]{id,description,conditions,plot_effect_score}:
        string,string,string,int

        

```
