"""The Outpost: the engine's own test world for the d20 rules and the packs a world requires. Generic people, places
and things, only what the tests in packs/d20/tests and tests/ need: a keep and its yard (a ring by old law), a road
out, open flats of deep sand with a vein and something burrowing under them, a ridge with a hidden spring that only
the hill folk know, a market with a trader and her casks, and a seep two steps from the flats.

    uv run embody --as gm --author load tests/fixtures/worlds/outpost
    uv run embody --as you join outpost Warden

Not a story: no rails, no timers, no dialog worth reading. The world's own scripts are the few the rules need:
creep (a quiet step on deep sand), ward_toggle (a belt ward's switch) and trader_on (a trader who turns a shard of
ember into a full skin, so a trade is not a gift).
"""

from packs.d20.pack import install_rules

WORLD = {
    "id": "outpost",
    "name": "The Outpost",
    "seed": 23,
    "description": "A test world for the d20 rules: a keep, a yard, a road, open sand, a ridge, a market.",
    "requires": ["d20", "village", "vehicles", "beasts"],
}

FACTIONS = ["the Garrison", "the Hill Folk", "the Rivals", "the Traders"]

WARDEN = {"faction": "the Garrison", "playable": True, "body": 2, "wits": 3, "will": 3,
          "skills": {"blade": 1, "parley": 2, "lore": 1, "resolve": 1},
          "description": "The warden of the keep.", "brief": "You are the Warden. Keep the keep."}
CAPTAIN = {"faction": "the Garrison", "playable": True, "body": 4, "wits": 2, "will": 3, "skills": {"blade": 3, "resolve": 2},
           "hp": 8, "max_hp": 8, "description": "The captain of the keep's guard.", "brief": "You are the Captain."}
STRANGER = {"faction": "the Rivals", "playable": True, "body": 3, "wits": 3, "will": 3,
            "skills": {"blade": 3, "stealth": 1, "resolve": 2}, "hp": 7, "max_hp": 7,
            "secret": ["dialog", "gives", "gave", "faction"],
            "description": "A stranger in the keep, quiet, with a blade.", "brief": "You are the Stranger."}
TRADER = {"faction": "the Traders", "playable": True, "body": 2, "wits": 4, "will": 3, "skills": {"parley": 3, "lore": 2, "resolve": 1},
          "description": "The trader at the market, a tally on a cord.", "brief": "You are the Trader. Ember in, water out."}
SCOUT = {"faction": "the Hill Folk", "playable": True, "body": 3, "wits": 3, "will": 2,
         "skills": {"blade": 2, "stealth": 2, "survival": 3},
         "description": "A scout of the hill folk.", "brief": "You are the Scout. You know the way down to the spring."}
ELDER = {"faction": "the Hill Folk", "body": 1, "wits": 4, "will": 5, "skills": {"lore": 3, "resolve": 3, "parley": 2},
         "description": "The elder of the hill folk, by the spring."}
LOOKOUT = {"faction": "the Hill Folk", "playable": True, "body": 2, "wits": 3, "will": 2,
           "skills": {"stealth": 3, "survival": 3, "blade": 1},
           "description": "A young lookout on the ridge.", "brief": "You are the Lookout. Watch the keep."}

STANDINGS = {
    "Warden": {"the Garrison": 5, "the Hill Folk": -1, "the Rivals": -3, "the Traders": 0},
    "Scout": {"the Hill Folk": 5, "the Garrison": -2, "the Rivals": -5, "the Traders": 0},
}

BLADE = {"weapon": True, "damage": 2, "bonus": 0, "portable": True}


def define(s):
    """Schemas. The scripts are the files in scripts/ and the packs. Safe to run again."""
    s.define_schema("person", extends="combatant", doc="Someone of the outpost: walks, carries, talks, and fights by the rules.",
                    state={"dialog": {}, "default_line": "Hm.", "gives": {}, "gave": {}, "asleep": False, "follows": None,
                           "secret": ["dialog", "gives", "gave"]},
                    actions={
                        "go": {"script": "go", "doc": "Walk to a connected place (loud on deep sand)", "targets": "place",
                               "scope": "exits", "duration": 10},
                        "creep": {"script": "creep", "doc": "Walk quietly: twice as long, the sand does not hear you",
                                  "targets": "place", "scope": "exits", "duration": 20},
                        "take": {"script": "take", "doc": "Pick something up", "targets": "thing", "scope": "here"},
                        "drop": {"script": "drop", "doc": "Put down something you hold", "targets": "thing", "scope": "held"},
                        "give": {"script": "give", "doc": "Hand something you hold to someone here", "targets": "creature",
                                 "scope": "here", "params": {"item": "id or name of a thing you hold"}},
                        "show": {"script": "show", "doc": "Show something you hold to someone here; they read it, you keep it",
                                 "targets": "creature", "scope": "here", "params": {"item": "id or name of a thing you hold"}},
                        "talk": {"script": "talk", "doc": "Talk to someone about something", "targets": "creature", "scope": "here",
                                 "duration": 2, "params": {"about": "the topic, in your words"}},
                        "follow": {"script": "follow", "doc": "Go where they go, until you stay", "targets": "creature", "scope": "here"},
                        "stay": {"script": "stay", "doc": "Stop following"},
                        "watch": {"script": "watch", "doc": "Look into the next place without stepping in", "targets": "place",
                                  "scope": "exits", "duration": 5},
                    },
                    listeners=[{"script": "person_on", "kinds": ["talked"], "unless_embodied": True}])
    s.define_schema("fighter", extends="person", doc="A person who fights without a mind: in a duel, or against the outlawed.",
                    behaviors=[{"script": "fighter_tick", "every": 6}])
    s.define_schema("trader", extends="person", doc="Trades ember for water.",
                    listeners=[{"script": "trader_on", "kinds": ["given"]}])
    s.define_schema("letter", extends="thing", doc="Something with writing on it. Paper rides in a pocket: no bulk.",
                    state={"text": "", "portable": True, "bulk": 0},
                    actions={"read": {"script": "read", "doc": "Read what is written"}})
    s.define_schema("ward", extends="thing", doc="A belt ward. On, it hardens against anything fast.",
                    state={"portable": True, "ward": True, "on": True},
                    actions={"toggle": {"script": "ward_toggle", "doc": "Switch it on or off"}})


def populate(s):
    """Places, people, things, standings, rules and the clock."""
    root = s.summary()["root"]
    keep = s.spawn("place", root, "The Keep", state={"description": "A stone keep with a cistern under the floor."})["id"]
    yard = s.spawn("place", root, "The Yard", state={"ring": True, "description": "Packed sand, a ring scratched in it."})["id"]
    road = s.spawn("place", root, "The Road", state={"open": True, "description": "The one road out, no shade."})["id"]
    flats = s.spawn("place", root, "The Flats", state={"open": True, "deep_sand": True, "tremor": 0,
                                                       "description": "Open sand, deep and soft. Every step rings."})["id"]
    ridge = s.spawn("place", root, "The Ridge", state={"description": "A spine of rock above the sand. Shade."})["id"]
    spring = s.spawn("place", root, "The Spring", state={"hidden": True, "known_to": "the Hill Folk", "water_source": True,
                                                         "description": "A cave under the ridge with a pool in it."})["id"]
    market = s.spawn("place", root, "The Market", state={"open": True, "description": "A flat where traders put down."})["id"]
    dunes = s.spawn("place", root, "The Dunes", state={"open": True, "deep_sand": True, "tremor": 2,
                                                       "description": "Soft dunes past the flats."})["id"]
    deep = s.spawn("place", root, "The Deep", state={"hidden": True, "description": "Under the sand."})["id"]
    oasis = s.spawn("place", root, "The Oasis", state={"open": True, "description": "A seep off the road."})["id"]
    s.connect(keep, yard)
    s.connect(yard, road)
    s.connect(road, flats)
    s.connect(road, market)
    s.connect(flats, ridge)
    s.connect(flats, dunes)
    s.connect(ridge, spring)
    s.connect(road, oasis)

    factions = {name: s.spawn("faction", root, name)["id"] for name in FACTIONS}

    # the keep
    warden = s.spawn("person", keep, "Warden", state=WARDEN)["id"]
    s.spawn("thing", warden, "Warden's blade", state=dict(BLADE))
    s.spawn("ward", warden, "Belt ward")
    s.spawn("waterskin", warden, "Waterskin", state={"left": 2})
    s.spawn("thing", keep, "The cistern", state={"portable": False, "water_source": True, "left": 12})
    stranger = s.spawn("fighter", keep, "Stranger", state=STRANGER)["id"]
    s.spawn("thing", stranger, "Stranger's blade", state={**BLADE, "bonus": 1})

    # the yard
    captain = s.spawn("fighter", yard, "Captain", state=CAPTAIN)["id"]
    s.spawn("thing", captain, "Captain's blade", state=dict(BLADE))
    s.spawn("thing", yard, "Rack of practice blades", state={"portable": False, "holds": ["weapon"], "room": 8})

    # the market: the casks are the traders' own, so nobody else's idle care walks there for water
    trader = s.spawn("trader", market, "Trader", state=TRADER)["id"]
    s.spawn("thing", market, "Water casks", state={"portable": False, "water_source": True, "left": 6, "keep_for": "the Traders"})

    # the flats, the dunes and what lives under them
    s.spawn("vein", flats, "Ore vein", state={"ember": 3})
    s.spawn("thresher", deep, "The Burrower", state={"home": deep})

    # the ridge and the spring
    scout = s.spawn("person", ridge, "Scout", state=SCOUT)["id"]
    s.spawn("thing", scout, "Scout's knife", state={"weapon": True, "damage": 1, "bonus": 1, "portable": True})
    s.spawn("waterskin", scout, "Scout's skin", state={"left": 3})
    s.spawn("person", ridge, "Lookout", state=LOOKOUT)
    s.spawn("person", spring, "Elder", state=ELDER)

    # the oasis: an endless seep two steps from the flats
    s.spawn("thing", oasis, "The seep", state={"portable": False, "water_source": True})

    by_name = {"Warden": warden, "Scout": scout}
    for who, table in STANDINGS.items():
        for fname, value in table.items():
            s.link(by_name[who], factions[fname], "standing", {"value": value, "public": True})

    install_rules(s, root)
    s.clock(run=False, turn=3)
    return s.summary()


def upgrade(s):
    """Nothing to bring forward: the rules again, which set_rule keeps idempotent."""
    install_rules(s, s.summary()["root"])
