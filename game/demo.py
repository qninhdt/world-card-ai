"""Demo world data and pre-generated card pool for offline play.

This module provides a complete world (no Architect API needed) and a pool
of pre-tagged cards (no Writer API needed) for the demo mode.
"""

from __future__ import annotations

from agents.schemas import (
    FunctionCall,
    NPCDef,
    SeasonDef,
    PlayerCharacterDef,
    PlotNodeDef,
    RelationshipDef,
    StatDef,
    TagDef,
    WorldGenSchema,
)
from cards.models import ChoiceCard, Choice


def get_demo_world() -> WorldGenSchema:
    """Return a medieval kingdom demo world."""
    return WorldGenSchema(
        world_name="Kingdom of Ardenvale",
        world_description=(
            "A medieval kingdom balanced on a knife's edge between power and ruin. "
            "The crown bears heavy, alliances shift like sand, and winter always comes too soon."
        ),
        era="High Medieval",
        starting_year=1066,
        resurrection_mechanic="The crown passes to a new heir, inheriting the burdens of the realm.",
        resurrection_flavor="A new ruler rises. The kingdom remembers... faintly.",
        player_character=PlayerCharacterDef(
            id="player",
            name="The Young Sovereign",
            role="Ruler of Ardenvale",
            description="A young ruler thrust onto the throne by fate. Untested, but not without potential.",
            traits=["ambitious", "idealistic", "untested"],
        ),
        stats=[
            StatDef(id="treasury", name="Treasury", description="Gold and wealth of the kingdom", icon="💰"),
            StatDef(id="military", name="Military", description="Strength of the armies", icon="⚔️"),
            StatDef(id="faith", name="Faith", description="The church's influence and the people's devotion", icon="✝️"),
            StatDef(id="people", name="People", description="The happiness and loyalty of the common folk", icon="👥"),
        ],
        npcs=[
            NPCDef(id="chancellor", name="Lord Aldric", role="Chancellor",
                   description="Shrewd advisor who always finds the pragmatic path.",
                   traits=["pragmatic", "calculating"]),
            NPCDef(id="general", name="Commander Elara", role="General",
                   description="Iron-willed warrior who values strength above all.",
                   traits=["brave", "stern"]),
            NPCDef(id="bishop", name="Father Caelan", role="Bishop",
                   description="Pious but politically savvy clergyman.",
                   traits=["devout", "cunning"]),
            NPCDef(id="merchant", name="Mira Goldhand", role="Trade Guild Master",
                   description="Wealthy merchant with connections everywhere.",
                   traits=["greedy", "resourceful"]),
            NPCDef(id="spymaster", name="The Whisper", role="Spymaster",
                   description="Nobody knows their real name. Information is their currency.",
                   traits=["secretive", "perceptive"]),
            NPCDef(id="rebel_leader", name="Scarlet", role="Leader of the Red Masks",
                   description="A charismatic revolutionary who speaks for the downtrodden.",
                   traits=["passionate", "reckless"], enabled=False),
            NPCDef(id="dragon_knight", name="Sir Obsidian", role="Knight of the Old Order",
                   description="A legendary knight thought to be myth.",
                   traits=["honorable", "ancient"], enabled=False),
        ],
        relationships=[
            RelationshipDef(a="player", b="chancellor", relationship="Your most trusted (and manipulative) advisor."),
            RelationshipDef(a="player", b="general", relationship="Loyal commander who expects strength from the throne."),
            RelationshipDef(a="chancellor", b="merchant", relationship="Old business partners with shared secrets."),
            RelationshipDef(a="bishop", b="spymaster", relationship="Bitter enemies — faith vs. shadow."),
        ],
        tags=[
            TagDef(id="investigated_raids", name="Investigated Raids", description="You looked into the northern raids"),
            TagDef(id="ignored_raids", name="Ignored Raids", description="You ignored the northern raids"),
            TagDef(id="traitor_identified", name="Traitor Identified", description="You know who the traitor is"),
            TagDef(id="traitor_punished", name="Traitor Punished", description="The traitor was brought to justice"),
            TagDef(id="traitor_forgiven", name="Traitor Forgiven", description="You showed mercy to the traitor"),
            TagDef(id="rebels_empowered", name="Rebels Empowered", description="The Red Masks grow in power"),
            TagDef(id="rebels_suppressed", name="Rebels Suppressed", description="The Red Masks were dealt with"),
            TagDef(id="border_fallen", name="Border Fallen", description="The northern border has collapsed"),
            TagDef(id="guild_favor", name="Guild Favor", description="The trade guild favors you"),
            TagDef(id="spy_network", name="Spy Network", description="You have a network of informants"),
            TagDef(id="explored_vault", name="Explored Vault", description="You explored the hidden vault"),
            TagDef(id="preserved_knowledge", name="Preserved Knowledge", description="You saved forbidden texts"),
        ],
        plot_nodes=[
            PlotNodeDef(
                id="border_raids",
                plot_description="Raids from the northern frontier intensify. Reports suggest they are organized, not random. Someone is funding the raiders.",
                condition="elapsed_days > 30",
                next_nodes=["discover_conspiracy", "border_war"],
            ),
            PlotNodeDef(
                id="discover_conspiracy",
                plot_description="Evidence mounts that a powerful noble within the kingdom is secretly arming the northern raiders.",
                condition="'investigated_raids' in tags and stats['military'] > 30",
                calls=[FunctionCall(name="enable_npc", params={"npc_id": "rebel_leader"})],
                next_nodes=["confront_traitor", "civil_war"],
            ),
            PlotNodeDef(
                id="border_war",
                plot_description="The raids escalate into a full border war. The kingdom must rally its armies.",
                condition="'ignored_raids' in tags and stats['military'] > 40",
                next_nodes=["confront_traitor", "ending_conquest"],
            ),
            PlotNodeDef(
                id="confront_traitor",
                plot_description="The traitor reveals themselves. A confrontation is inevitable.",
                condition="'traitor_identified' in tags and elapsed_days > 120",
                calls=[FunctionCall(name="enable_npc", params={"npc_id": "dragon_knight"})],
                next_nodes=["ending_justice", "ending_mercy"],
            ),
            PlotNodeDef(
                id="civil_war",
                plot_description="The kingdom splits in two. Rebels storm the capital while enemies mass at the borders.",
                condition="'rebels_empowered' in tags and stats['people'] < 40",
                next_nodes=["ending_conquest"],
            ),
            PlotNodeDef(
                id="ending_justice",
                plot_description="The traitor is brought to justice. The kingdom is united under a reformed crown.",
                condition="'traitor_punished' in tags and stats['military'] > 50 and stats['faith'] > 40",
                is_ending=True,
                ending_text="Through fire and betrayal, you forged a kingdom of iron justice. History will remember you as The Unyielding.",
            ),
            PlotNodeDef(
                id="ending_mercy",
                plot_description="You offer the traitor clemency. The kingdom heals through forgiveness.",
                condition="'traitor_forgiven' in tags and stats['people'] > 50 and stats['faith'] > 50",
                is_ending=True,
                ending_text="You chose mercy where others demanded blood. The bards sing of The Merciful.",
            ),
            PlotNodeDef(
                id="ending_conquest",
                plot_description="The kingdom falls to external conquest.",
                condition="'border_fallen' in tags and stats['military'] < 30",
                is_ending=True,
                ending_text="The walls crumbled. The flags burned. Your name became a cautionary tale.",
            ),
        ],
        seasons=[
            SeasonDef(name="Spring", description="Flowers bloom, trade routes open.", icon="🌸"),
            SeasonDef(name="Summer", description="The sun blazes. Armies march.", icon="☀️"),
            SeasonDef(name="Autumn", description="Harvest time. The granaries fill.", icon="🍂"),
            SeasonDef(name="Winter", description="The frost bites deep. Resources dwindle.", icon="❄️"),
        ],
    )


# ── Pre-generated Card Pool ────────────────────────────────────────────────

# Helper to make FunctionCall-based choices
def _fc(_func_name: str, **params) -> FunctionCall:
    return FunctionCall(name=_func_name, params=params)


def _stat(**kv) -> list[FunctionCall]:
    return [FunctionCall(name="update_stat", params=kv)]


def get_demo_card_pool() -> list:
    """Return a pool of ~30 pre-generated cards for demo mode."""
    return [
        # ── Treasury-focused ────────────────────────────────────────────
        ChoiceCard(
            id="demo_tax_01", title="Tax Reform", character="chancellor",
            description="The Chancellor proposes a new tax scheme to fill the coffers, but the people won't like it.",
            left=Choice(text="Raise taxes", calls=_stat(treasury=15, people=-10)),
            right=Choice(text="Keep current rates", calls=_stat(treasury=-5, people=5)),
            source="common",
        ),
        ChoiceCard(
            id="demo_trade_01", title="Foreign Traders", character="merchant",
            description="A caravan from distant lands arrives. They offer exotic goods... at a price.",
            left=Choice(text="Welcome them", calls=_stat(treasury=-8, people=5)),
            right=Choice(text="Turn them away", calls=_stat(treasury=3, people=-3)),
            source="common",
        ),
        ChoiceCard(
            id="demo_bribe_01", title="A Generous Offer", character="merchant",
            description="The guild master slides a heavy purse across the table. 'A gift. No strings attached.'",
            left=Choice(text="Accept it", calls=_stat(treasury=10, faith=-5) + [_fc("add_tag", tag_id="guild_favor")]),
            right=Choice(text="Refuse", calls=_stat(treasury=-3, faith=3)),
            source="common",
        ),

        # ── Military-focused ───────────────────────────────────────────
        ChoiceCard(
            id="demo_recruit_01", title="Military Recruitment", character="general",
            description="The General demands more soldiers. Conscription or gold — either way, it costs.",
            left=Choice(text="Conscript from villages", calls=_stat(military=12, people=-10)),
            right=Choice(text="Hire mercenaries", calls=_stat(military=8, treasury=-12)),
            source="common",
        ),
        ChoiceCard(
            id="demo_border_01", title="Patrol Report", character="general",
            description="'The northern border is quiet. Too quiet.' The General eyes the map with suspicion.",
            left=Choice(text="Double patrols", calls=_stat(military=-5, treasury=-3) + [_fc("add_tag", tag_id="investigated_raids")]),
            right=Choice(text="Ignore it", calls=_stat(military=3) + [_fc("add_tag", tag_id="ignored_raids")]),
            source="common",
        ),
        ChoiceCard(
            id="demo_duel_01", title="A Challenge", character="general",
            description="A foreign champion demands trial by combat. Refusing would shame the crown.",
            left=Choice(text="Accept the duel", calls=_stat(military=8, people=5)),
            right=Choice(text="Negotiate instead", calls=_stat(military=-5, treasury=5, people=-3)),
            source="common",
        ),

        # ── Faith-focused ──────────────────────────────────────────────
        ChoiceCard(
            id="demo_heresy_01", title="Heretic Preacher", character="bishop",
            description="A wandering preacher spreads dangerous ideas. The Bishop demands action.",
            left=Choice(text="Arrest the preacher", calls=_stat(faith=10, people=-8)),
            right=Choice(text="Let them speak", calls=_stat(faith=-8, people=5)),
            source="common",
        ),
        ChoiceCard(
            id="demo_blessing_01", title="Festival of Light", character="bishop",
            description="The annual blessing ceremony approaches. A grand display would inspire the faithful.",
            left=Choice(text="Spare no expense", calls=_stat(faith=10, people=5, treasury=-12)),
            right=Choice(text="Keep it modest", calls=_stat(faith=-3, treasury=3)),
            source="common",
        ),

        # ── People-focused ─────────────────────────────────────────────
        ChoiceCard(
            id="demo_feast_01", title="A Grand Feast", character="chancellor",
            description="The people suffer through a hard season. A feast could lift spirits... or bankrupt the crown.",
            left=Choice(text="Hold the feast", calls=_stat(people=12, treasury=-10)),
            right=Choice(text="Save the gold", calls=_stat(people=-5, treasury=5)),
            source="common",
        ),
        ChoiceCard(
            id="demo_plague_01", title="Sickness Spreads", character="chancellor",
            description="A strange illness creeps through the lower wards. Healers demand funding.",
            left=Choice(text="Fund the healers", calls=_stat(people=8, treasury=-10)),
            right=Choice(text="Quarantine the sick", calls=_stat(people=-10, military=-3, treasury=3)),
            source="common",
        ),
        ChoiceCard(
            id="demo_petition_01", title="Peasant's Plea", character="narrator",
            description="A trembling farmer kneels before you, begging for seed grain.",
            left=Choice(text="Grant the grain", calls=_stat(people=8, treasury=-5)),
            right=Choice(text="Deny the request", calls=_stat(people=-8, treasury=3)),
            source="common",
        ),

        # ── Spymaster / intrigue ───────────────────────────────────────
        ChoiceCard(
            id="demo_spy_01", title="Whispers in the Dark", character="spymaster",
            description="'There's a plot. I can root it out... for a price.'",
            left=Choice(text="Pay for the information", calls=_stat(treasury=-8) + [_fc("add_tag", tag_id="spy_network")]),
            right=Choice(text="Ignore the whispers", calls=_stat(military=-3)),
            source="common",
        ),
        ChoiceCard(
            id="demo_spy_03", title="The Spy's Gambit", character="spymaster",
            description="'I've infiltrated the raiders camp. I can sabotage them from within.'",
            left=Choice(text="Sabotage them", calls=_stat(military=8, treasury=-5) + [_fc("add_tag", tag_id="traitor_identified")]),
            right=Choice(text="Buy their secrets", calls=_stat(treasury=-10, military=5)),
            source="common",
        ),

        # ── Multi-stat dilemmas ────────────────────────────────────────
        ChoiceCard(
            id="demo_refugee_01", title="Refugees at the Gates", character="general",
            description="Hundreds of refugees flee the border conflict. Opening the gates means feeding them.",
            left=Choice(text="Open the gates", calls=_stat(people=10, treasury=-8, military=-3)),
            right=Choice(text="Bar the gates", calls=_stat(people=-12, military=5, faith=-5)),
            source="common",
        ),
        ChoiceCard(
            id="demo_marriage_01", title="Royal Marriage", character="chancellor",
            description="A powerful neighboring kingdom offers their heir in marriage. An alliance — or a cage?",
            left=Choice(text="Accept the match", calls=_stat(treasury=10, military=5, people=-5)),
            right=Choice(text="Decline politely", calls=_stat(people=5, treasury=-5, military=-3)),
            source="common",
        ),
        ChoiceCard(
            id="demo_riot_01", title="Market Riot", character="spymaster",
            description="The market erupted. Angry mobs clash with guards. Someone orchestrated this.",
            left=Choice(text="Crack down hard", calls=_stat(people=-12, military=5)),
            right=Choice(text="Address their grievances", calls=_stat(people=8, treasury=-8)),
            source="common",
        ),
        ChoiceCard(
            id="demo_rebel_rumor_01", title="Red Masks Sighted", character="spymaster",
            description="'The Red Masks have been seen near the capital. They're getting bolder.'",
            left=Choice(text="Send the Whisper", calls=_stat(treasury=-5, military=3) + [_fc("add_tag", tag_id="rebels_suppressed")]),
            right=Choice(text="Do nothing", calls=_stat(people=-3) + [_fc("add_tag", tag_id="rebels_empowered")]),
            source="common",
        ),
        
        # ── Advanced Mechanics (Events & Time) ─────────────────────────
        ChoiceCard(
            id="demo_tournament_01", title="A Grand Tournament", character="general",
            description="The General suggests hosting a grand tournament to raise morale and military strength.",
            left=Choice(text="Declare the Tournament", calls=[
                _fc("add_event", type="progress", event_id="grand_tournament", name="Grand Tournament Preparations",
                    description="Knights from across the realm gather.", icon="🎪", target=5, progress_label="Knights arrived"),
                _fc("update_stat", treasury=-15, people=10, military=5)
            ]),
            right=Choice(text="It's a waste of gold", calls=_stat(military=-5, people=-5)),
            source="common",
        ),
        ChoiceCard(
            id="demo_winter_event_01", title="The Long Winter", character="chancellor",
            description="'The crops have completely failed in the north. The refugees say a supernatural winter approaches.'",
            left=Choice(text="Prepare rationing", calls=[
                _fc("add_event", type="phase", event_id="long_winter", name="The Long Winter", description="An unnatural chill settles over the kingdom.", icon="❄️",
                    phases=[
                        {"name": "Early Frost", "description": "The rivers freeze."},
                        {"name": "Deep Cold", "description": "People begin to starve."},
                        {"name": "The Thaw", "description": "The snow finally recedes."}
                    ]),
                _fc("update_stat", treasury=-10, people=-5)
            ]),
            right=Choice(text="Only worry about the capital", calls=_stat(treasury=5, people=-15, faith=-10)),
            source="common",
        ),
        ChoiceCard(
            id="demo_time_skip_01", title="A Long Journey", character="bishop",
            description="'The High Septon demands my presence at the Holy Citadel. I shall be gone for a long time.'",
            left=Choice(text="Grant leave", calls=[
                _fc("advance_time", days=14),
                _fc("update_stat", faith=15, treasury=-5)
            ]),
            right=Choice(text="Forbid the journey", calls=_stat(faith=-15, military=5)),
            source="common",
        ),
    ]
