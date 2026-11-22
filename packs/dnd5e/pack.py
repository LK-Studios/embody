"""D&D 5e combat on top of d20 and sheet. Opt-in: a world names it after them in its manifest
(`"requires": ["village", "d20", "sheet", "dnd5e"]`) and calls `install_rules(s, root)` from here after d20's. The fight
then runs by 5e: initiative and turns, attack rolls against armour class, damage dice, crits, death saves, the action
economy, conditions, saving throws, resistances and spell slots. Thirst, factions, duels, sleep and the sheet's skills
stay d20's. Where the 2014 and 2024 rules differ this follows 2024 (SRD 5.2); the mechanics are summarised here in our own
words, no rulebook text.

The numbers, so a narrator can explain a roll:

- Abilities. A body's six scores come from its `scores` ({"str": 16, ...}) when it has one, else its sheet (str force,
  dex poise, con endurance, int cognition, wis acuity, cha projection), else d20's stats (10 + 2 x body, wits or will).
  The modifier is (score - 10) // 2. Proficiency is `prof` on the body, else 2 + (level - 1) // 4 by `level` (or `cr`),
  else 2. Skill checks stay d20's `check` (d20 + the sheet's modifier and rank, the rank being the 5e proficiency).
- A fight. The first hostile deed in a place (an attack, a shot, a grapple, a harmful spell, a fighter turning on a
  foe) starts one: every living body there rolls initiative, d20 + dex modifier + `init_bonus` (a sleeper rolls with
  disadvantage: surprised). Bodies nobody plays roll at once. A body someone plays rolls its own: the
  `roll_initiative` event calls for it ("Roll initiative!"), and `initiative` (free) answers, with `roll` set to what
  the player's own d20 shows, or without it and the world rolls. Until every roll is in, no turn opens and the deed
  that started the fight waits for its turn; after the played turn's wait (`turn_wait`) the world rolls for whoever has
  not (the root's `dnd5e.player_rolls` false has the world roll for everyone at once). Highest first; ties go to the
  higher dex, then to the body nobody plays. The `initiative` event lists the order. Whoever arrives mid-fight rolls and
  joins (a played body arriving while the rolls are out rolls its own); whoever leaves the place leaves the fight. While it
  lasts, only the body whose turn it is acts: anyone else is refused with whose turn it is. Talking, yielding and
  `end` are free any time; taking, dropping and giving are free on your turn. A fight ends when a round passes with no
  two standing bodies still at odds and nobody dying (`fight_over`). Rounds are 6 seconds.
- A turn: one action, one bonus action, one move (leaving the place) and one reaction a round. Attack, shoot, cast (most
  spells), dodge, dash, disengage, help, hide, grapple, shove, escape, tend, kill, check, threaten, parley and anything a
  world adds are actions; offhand and some spells are bonus actions; `go` is your move (`dash` gives another). Your turn
  ends when your action is spent and you have no bonus action you could take, or when you say `end`. A body played by
  nobody takes its turn at once: it strikes whoever struck it, or anyone its side has outlawed, and nobody else.
  `extra_attacks` on a body (fighters at 5) is how many more blows its Attack action holds.
- An attack: d20 + the weapon's ability modifier (str; dex for ranged; the better for finesse) + proficiency (always
  for bare hands; `weapon_prof` on a body limits it to those categories or kinds) + the weapon's `bonus`, against the
  target's armour class. A natural 20 always hits and doubles the damage dice (a crit; `crit_range` 19 widens it); a
  natural 1 always misses. Damage is the weapon's `dice` + the same modifier + its `bonus`, of its `dtype`; bare hands do
  1 + str. Advantage and disadvantage (2d20, the better or the worse) come from conditions and never stack: they cancel.
  A shot with a foe close by (someone at odds with you, standing here) has disadvantage; cover where the target stands
  adds to its armour class against shots. A melee blow on an unconscious or paralysed body is a crit when it hits.
- Armour class: `ac` on a body when it has one (a stat block); else the best armour it carries (a thing with `armor`
  {ac, dex_cap}: light none, medium 2, heavy 0) + its dex modifier up to the cap, or 10 + dex with none (`unarmored`
  "con" or "wis" adds that too); + a shield (`armor` {shield: true, ac: 2}) + `ac_bonus` + what spells add.
- Damage: `resist`, `immune` and `vulnerable` lists on a body (damage types, or "all") halve, cancel or double it;
  `temp_hp` soaks it first. At 0 hp a body is down: unconscious and prone, and dying. On each of its turns it rolls a
  death save, d20 with no modifiers: 10 or more is a success, a 1 is two failures, a 20 brings it back at 1 hp. Three
  successes and it is stable (still down; it wakes at 1 hp after 1d4 hours); three failures and it dies. A blow on a
  dying body is a failure (a crit, two); damage of the body's max hp or more past 0 kills outright. Any healing gets it
  up. `knockout` on an attack (a melee blow) leaves the one it drops stable instead of dying, and blows in a duel always
  knock out. `dies_at_zero` on a body (a beast, a mook) dies at 0 instead. A deliberate `kill` still finishes the down.
- Saving throws: d20 + the ability modifier + proficiency when the ability is in the body's `saves`. Paralysed,
  stunned, unconscious and petrified bodies fail str and dex saves; a dodging body has advantage on dex saves;
  `save_adv` on a body (a list of tags: "poison", "charmed") gives advantage against those.
- Conditions, on a body's `conditions` ({name: {by, rounds, until, save}}): blinded, charmed, frightened, grappled,
  incapacitated, invisible, paralyzed, petrified, poisoned, prone, restrained, stunned, unconscious, and exhaustion as a
  level (`exhaustion`, -2 to every d20 test a level; 6 is death). Each one does what 5e says to attacks, saves and
  movement. `rounds` count down at the end of the bearer's turns; a `save` is rolled again at each turn's end and ends it.
- Actions: `dodge` (attacks on you have disadvantage, dex saves advantage, until your next turn; `brace` is the same),
  `dash` (another move), `disengage` (leaving provokes nothing), `help` (an ally's next attack on a foe of yours has
  advantage), `hide` (stealth against 15: unseen until you attack), `grapple` and `shove` (one of your attacks: the
  target saves str or dex against 8 + your str modifier + proficiency, or is grappled, or knocked prone), `escape`
  (athletics or acrobatics against that number), `stand` (half your move: up from prone), `offhand` (a bonus blow with
  a light weapon in the other hand, no modifier to its damage), `end`. Leaving a place while a foe there has its
  reaction draws an opportunity attack, unless you disengaged.
- Spells: a body's `spellcasting` {ability, spells, slots, slots_max, pact}. `cast` (params `spell`, `level`) spends a
  slot of that level or higher (cantrips none); spell attack d20 + proficiency + the ability modifier, save DC 8 +
  proficiency + the modifier. The world's catalogue is the root's `spells` (this pack's set laid over the world's own).
  Concentration holds one spell at a time; damage asks a con save against the larger of 10 and half the damage. Cantrip
  dice grow at levels 5, 11 and 17. A body that knows `shield` uses its reaction to turn a hit into a miss when +5 does.
- Rest: `rest` is a short rest (an hour): spend hit dice (params `dice`), each heals the die + con. Sleeping 8 hours is a
  long rest when you wake (once a day): full hp, half your hit dice back, every slot back, a level of exhaustion gone.
  Rest no longer mends a point a beat: in 5e only rest, spells and medicine heal. `tend` with medicine in hand (a thing
  with `doses` and `heals`, dice like "2d4+2") heals; bare hands roll medicine (wis) against 10 to stabilise the dying.
- `stats` (free) tells a body its own numbers: hp, armour class, proficiency, initiative, attacks, saves, spells, slots,
  conditions and what is left of its turn.

Every number a world might tune lives on the root's `dnd5e` (costs of verbs, the round, how long a played turn waits);
the catalogues are the root's `spells`, and WEAPONS, ARMOR and CLASSES here for builders.
"""

PACK = {"name": "dnd5e", "description": "D&D 5e combat: initiative and turns, armour class, damage dice, crits, death saves, "
                                         "the action economy, conditions, saves, resistances and spell slots."}

RULES = [
    {"id": "dnd5e-combat", "date": "2026-11-22",
     "was": "A fight had no turns: a blow was an opposed d20 + body + blade, a hit did the weapon's fixed damage, and at 0 "
            "hp you were down until someone tended you or rest got you up. Rest mended a point a beat.",
     "now": "Fights run by D&D 5e. The first hostile deed rolls initiative for everyone in the place, and only the body "
            "whose turn it is acts (an action, a bonus action, a move, a reaction). Attacks roll d20 + modifier + "
            "proficiency against armour class; damage is dice; a natural 20 crits. At 0 hp you are unconscious and "
            "roll death saves on your turns. Conditions, saving throws, resistances and spell slots are in. Rest no "
            "longer mends a point a beat: short rests spend hit dice, a night's sleep restores you. `stats` shows your "
            "numbers.",
     "retired": ["braced", "wounded"],
     "recheck": ["plans that fight by the old numbers", "notes that count hp in quarters",
                 "plans that wait for rest to mend a wound"],
     "guide": ["player", "mind", "narrator"]},
    {"id": "dnd5e-roll-initiative", "date": "2026-11-22",
     "was": "The world rolled everyone's initiative the moment a fight started, players' included.",
     "now": "A played body rolls its own initiative. When a fight starts, `roll_initiative` calls for it: answer with "
            "`initiative` and `roll` set to what your own d20 shows, or `initiative` alone and the world rolls for you. "
            "The turns start once every roll is in (the world rolls for anyone who has not answered after a turn's "
            "wait), and the deed that started the fight lands on its turn.",
     "retired": [],
     "recheck": ["plans that expect the first blow to land the moment it is struck"],
     "guide": ["player", "mind", "narrator"]},
]

ROUND = 6  # seconds

# what each verb costs in a fight: free (any time), object (free, on your turn), action, attack (one of the Attack
# action's blows), bonus, move. Anything not listed is an action. A world lays its own over this on the root's dnd5e.costs.
COSTS = {
    "talk": "free", "yield": "free", "end": "free", "stats": "free", "initiative": "free", "read": "free", "show": "free", "watch": "free",
    "take": "object", "drop": "object", "give": "object", "put": "object", "buy": "object", "draw": "object",
    "attack": "attack", "shoot": "attack", "grapple": "attack", "shove": "attack",
    "offhand": "bonus",
    "go": "move", "stand": "move", "crawl": "move", "follow": "free", "stay": "free",
}

SETTINGS = {"round": ROUND, "turn_wait": 120, "costs": {}, "npc_gap": 0.5, "player_rolls": True}

# how a body's card words its way out under these rules (the root's condition_notes; a world's own words win)
CONDITION_NOTES = {
    "hurt": "half its hp or less; in 5e that costs nothing on its rolls. Rest (a short rest spends hit dice), medicine or a spell heals it",
    "down (wounds)": "unconscious at 0 hp. Dying, it rolls a death save each turn: three successes and it is stable, three "
                     "failures and it dies. Any healing gets it up; tend (medicine against 10) stabilises it",
}

# ---- weapons, armour and classes (SRD 5.2 numbers) -------------------------------------------------------------------

WEAPONS = {
    "club": {"dice": "1d4", "dtype": "bludgeoning", "category": "simple", "properties": ["light"]},
    "dagger": {"dice": "1d4", "dtype": "piercing", "category": "simple", "properties": ["finesse", "light", "thrown"]},
    "greatclub": {"dice": "1d8", "dtype": "bludgeoning", "category": "simple", "properties": ["two-handed"]},
    "handaxe": {"dice": "1d6", "dtype": "slashing", "category": "simple", "properties": ["light", "thrown"]},
    "javelin": {"dice": "1d6", "dtype": "piercing", "category": "simple", "properties": ["thrown"]},
    "mace": {"dice": "1d6", "dtype": "bludgeoning", "category": "simple", "properties": []},
    "quarterstaff": {"dice": "1d6", "dtype": "bludgeoning", "category": "simple", "properties": ["versatile"], "versatile": "1d8"},
    "sickle": {"dice": "1d4", "dtype": "slashing", "category": "simple", "properties": ["light"]},
    "spear": {"dice": "1d6", "dtype": "piercing", "category": "simple", "properties": ["thrown", "versatile"], "versatile": "1d8"},
    "light crossbow": {"dice": "1d8", "dtype": "piercing", "category": "simple", "properties": ["ammunition", "loading", "two-handed"],
                       "ranged": True, "ammo": "bolt"},
    "shortbow": {"dice": "1d6", "dtype": "piercing", "category": "simple", "properties": ["ammunition", "two-handed"],
                 "ranged": True, "ammo": "arrow"},
    "sling": {"dice": "1d4", "dtype": "bludgeoning", "category": "simple", "properties": ["ammunition"], "ranged": True, "ammo": "bullet"},
    "battleaxe": {"dice": "1d8", "dtype": "slashing", "category": "martial", "properties": ["versatile"], "versatile": "1d10"},
    "glaive": {"dice": "1d10", "dtype": "slashing", "category": "martial", "properties": ["heavy", "reach", "two-handed"]},
    "greataxe": {"dice": "1d12", "dtype": "slashing", "category": "martial", "properties": ["heavy", "two-handed"]},
    "greatsword": {"dice": "2d6", "dtype": "slashing", "category": "martial", "properties": ["heavy", "two-handed"]},
    "longsword": {"dice": "1d8", "dtype": "slashing", "category": "martial", "properties": ["versatile"], "versatile": "1d10"},
    "maul": {"dice": "2d6", "dtype": "bludgeoning", "category": "martial", "properties": ["heavy", "two-handed"]},
    "rapier": {"dice": "1d8", "dtype": "piercing", "category": "martial", "properties": ["finesse"]},
    "scimitar": {"dice": "1d6", "dtype": "slashing", "category": "martial", "properties": ["finesse", "light"]},
    "shortsword": {"dice": "1d6", "dtype": "piercing", "category": "martial", "properties": ["finesse", "light"]},
    "trident": {"dice": "1d8", "dtype": "piercing", "category": "martial", "properties": ["thrown", "versatile"], "versatile": "1d10"},
    "warhammer": {"dice": "1d8", "dtype": "bludgeoning", "category": "martial", "properties": ["versatile"], "versatile": "1d10"},
    "whip": {"dice": "1d4", "dtype": "slashing", "category": "martial", "properties": ["finesse", "reach"]},
    "hand crossbow": {"dice": "1d6", "dtype": "piercing", "category": "martial", "properties": ["ammunition", "light", "loading"],
                      "ranged": True, "ammo": "bolt"},
    "heavy crossbow": {"dice": "1d10", "dtype": "piercing", "category": "martial", "properties": ["ammunition", "heavy", "loading", "two-handed"],
                       "ranged": True, "ammo": "bolt"},
    "longbow": {"dice": "1d8", "dtype": "piercing", "category": "martial", "properties": ["ammunition", "heavy", "two-handed"],
                "ranged": True, "ammo": "arrow"},
}

ARMOR = {
    "padded": {"ac": 11, "dex_cap": None, "weight": "light", "stealth_dis": True},
    "leather": {"ac": 11, "dex_cap": None, "weight": "light"},
    "studded leather": {"ac": 12, "dex_cap": None, "weight": "light"},
    "hide": {"ac": 12, "dex_cap": 2, "weight": "medium"},
    "chain shirt": {"ac": 13, "dex_cap": 2, "weight": "medium"},
    "scale mail": {"ac": 14, "dex_cap": 2, "weight": "medium", "stealth_dis": True},
    "breastplate": {"ac": 14, "dex_cap": 2, "weight": "medium"},
    "half plate": {"ac": 15, "dex_cap": 2, "weight": "medium", "stealth_dis": True},
    "ring mail": {"ac": 14, "dex_cap": 0, "weight": "heavy", "stealth_dis": True},
    "chain mail": {"ac": 16, "dex_cap": 0, "weight": "heavy", "stealth_dis": True},
    "splint": {"ac": 17, "dex_cap": 0, "weight": "heavy", "stealth_dis": True},
    "plate": {"ac": 18, "dex_cap": 0, "weight": "heavy", "stealth_dis": True},
    "shield": {"ac": 2, "shield": True},
}

# hit die, saving throws, spellcasting ability and kind (full, half, pact), extra attack levels, and the rest
CLASSES = {
    "barbarian": {"die": 12, "saves": ["str", "con"], "extra": [5], "unarmored": "con", "weapons": ["simple", "martial"]},
    "bard": {"die": 8, "saves": ["dex", "cha"], "cast": "cha", "caster": "full", "weapons": ["simple"]},
    "cleric": {"die": 8, "saves": ["wis", "cha"], "cast": "wis", "caster": "full", "weapons": ["simple"]},
    "druid": {"die": 8, "saves": ["int", "wis"], "cast": "wis", "caster": "full", "weapons": ["simple"]},
    "fighter": {"die": 10, "saves": ["str", "con"], "extra": [5, 11, 20], "weapons": ["simple", "martial"]},
    "monk": {"die": 8, "saves": ["str", "dex"], "extra": [5], "unarmored": "wis", "martial_arts": True, "weapons": ["simple"]},
    "paladin": {"die": 10, "saves": ["wis", "cha"], "cast": "cha", "caster": "half", "extra": [5], "weapons": ["simple", "martial"]},
    "ranger": {"die": 10, "saves": ["str", "dex"], "cast": "wis", "caster": "half", "extra": [5], "weapons": ["simple", "martial"]},
    "rogue": {"die": 8, "saves": ["dex", "int"], "sneak": True, "cunning": 2, "weapons": ["simple", "martial"]},
    "sorcerer": {"die": 6, "saves": ["con", "cha"], "cast": "cha", "caster": "full", "weapons": ["simple"]},
    "warlock": {"die": 8, "saves": ["wis", "cha"], "cast": "cha", "caster": "pact", "weapons": ["simple"]},
    "wizard": {"die": 6, "saves": ["int", "wis"], "cast": "int", "caster": "full", "weapons": ["simple"]},
}

# spell slots by caster level, from 1st level slots up
FULL_SLOTS = {1: [2], 2: [3], 3: [4, 2], 4: [4, 3], 5: [4, 3, 2], 6: [4, 3, 3], 7: [4, 3, 3, 1], 8: [4, 3, 3, 2],
              9: [4, 3, 3, 3, 1], 10: [4, 3, 3, 3, 2], 11: [4, 3, 3, 3, 2, 1], 12: [4, 3, 3, 3, 2, 1],
              13: [4, 3, 3, 3, 2, 1, 1], 14: [4, 3, 3, 3, 2, 1, 1], 15: [4, 3, 3, 3, 2, 1, 1, 1], 16: [4, 3, 3, 3, 2, 1, 1, 1],
              17: [4, 3, 3, 3, 2, 1, 1, 1, 1], 18: [4, 3, 3, 3, 3, 1, 1, 1, 1], 19: [4, 3, 3, 3, 3, 2, 1, 1, 1],
              20: [4, 3, 3, 3, 3, 2, 2, 1, 1]}
PACT_SLOTS = {1: (1, 1), 2: (2, 1), 3: (2, 2), 4: (2, 2), 5: (2, 3), 6: (2, 3), 7: (2, 4), 8: (2, 4), 9: (2, 5), 10: (2, 5),
              11: (3, 5), 12: (3, 5), 13: (3, 5), 14: (3, 5), 15: (3, 5), 16: (3, 5), 17: (4, 5), 18: (4, 5), 19: (4, 5), 20: (4, 5)}

# ---- the spell catalogue (SRD 5.2 mechanics, described in our own words) -------------------------------------------
# kind: attack (a spell attack roll), save (the target saves), auto (it simply lands), heal, buff (a condition on the
# target, no save). range: touch or here (someone in this place), sight (one way over too), self. area: everyone at odds
# with the caster here takes it too. cond: the condition it leaves (on a failed save, or on a buff's target).

SPELLS = {
    "fire bolt": {"level": 0, "kind": "attack", "attack": "ranged", "dice": "1d10", "dtype": "fire", "range": "sight",
                  "words": "a mote of fire flung at someone"},
    "ray of frost": {"level": 0, "kind": "attack", "attack": "ranged", "dice": "1d8", "dtype": "cold", "range": "sight",
                     "words": "a pale beam that numbs where it lands"},
    "eldritch blast": {"level": 0, "kind": "attack", "attack": "ranged", "dice": "1d10", "dtype": "force", "range": "sight",
                       "beams": True, "words": "a crackling beam; more beams at levels 5, 11 and 17"},
    "produce flame": {"level": 0, "kind": "attack", "attack": "ranged", "dice": "1d8", "dtype": "fire", "range": "here",
                      "words": "a flame in the palm, thrown"},
    "shocking grasp": {"level": 0, "kind": "attack", "attack": "melee", "dice": "1d8", "dtype": "lightning", "range": "touch",
                       "cond": {"name": "no_reactions", "rounds": 1, "ends": "start"},
                       "words": "a jolt by touch; the target cannot take reactions until its next turn"},
    "thorn whip": {"level": 0, "kind": "attack", "attack": "melee", "dice": "1d6", "dtype": "piercing", "range": "here",
                   "words": "a thorny vine lashes out"},
    "chill touch": {"level": 0, "kind": "attack", "attack": "melee", "dice": "1d10", "dtype": "necrotic", "range": "touch",
                    "words": "a grave-cold touch"},
    "sacred flame": {"level": 0, "kind": "save", "save": "dex", "dice": "1d8", "dtype": "radiant", "range": "sight",
                     "cover": False, "words": "radiance falls on someone; cover does not help them"},
    "vicious mockery": {"level": 0, "kind": "save", "save": "wis", "dice": "1d6", "dtype": "psychic", "range": "here",
                        "cond": {"name": "mocked", "once": True, "rounds": 1},
                        "words": "an insult with magic in it; they have disadvantage on their next attack"},
    "toll the dead": {"level": 0, "kind": "save", "save": "wis", "dice": "1d8", "hurt_dice": "1d12", "dtype": "necrotic",
                      "range": "sight", "words": "a dolorous bell; worse for the already hurt"},
    "magic missile": {"level": 1, "kind": "auto", "darts": 3, "dice": "1d4+1", "dtype": "force", "range": "sight",
                      "words": "three darts of force that never miss; one more for each slot level above 1st"},
    "cure wounds": {"level": 1, "kind": "heal", "dice": "2d8", "add_mod": True, "upcast": "2d8", "range": "touch",
                    "target": "ally", "words": "a touch that closes wounds"},
    "healing word": {"level": 1, "kind": "heal", "time": "bonus", "dice": "2d4", "add_mod": True, "upcast": "2d4",
                     "range": "here", "target": "ally", "words": "a word of power that heals at a distance"},
    "burning hands": {"level": 1, "kind": "save", "save": "dex", "dice": "3d6", "dtype": "fire", "half": True, "area": True,
                      "upcast": "1d6", "range": "here", "words": "a fan of flame"},
    "thunderwave": {"level": 1, "kind": "save", "save": "con", "dice": "2d8", "dtype": "thunder", "half": True, "area": True,
                    "upcast": "1d8", "range": "here", "words": "a wave of thunderous force"},
    "guiding bolt": {"level": 1, "kind": "attack", "attack": "ranged", "dice": "4d6", "dtype": "radiant", "upcast": "1d6",
                     "range": "sight", "cond": {"name": "guided", "once": True, "rounds": 1},
                     "words": "a flash of light; the next attack on the target has advantage"},
    "inflict wounds": {"level": 1, "kind": "save", "save": "con", "dice": "2d10", "dtype": "necrotic", "half": True,
                       "upcast": "1d10", "range": "touch", "words": "a necrotic touch"},
    "shield": {"level": 1, "kind": "buff", "time": "reaction", "range": "self", "target": "self",
               "cond": {"name": "shielded", "ac": 5, "rounds": 1, "ends": "start"},
               "words": "a barrier: +5 armour class until your next turn (cast as a reaction to a hit)"},
    "bless": {"level": 1, "kind": "buff", "conc": True, "range": "here", "target": "ally",
              "cond": {"name": "blessed", "die": "1d4", "rounds": 10}, "words": "+1d4 to attacks and saves for a minute"},
    "bane": {"level": 1, "kind": "save", "save": "cha", "conc": True, "range": "here",
             "cond": {"name": "baned", "die": "1d4", "rounds": 10}, "words": "-1d4 to attacks and saves for a minute"},
    "mage armor": {"level": 1, "kind": "buff", "range": "touch", "target": "ally",
                   "cond": {"name": "mage armor", "ac_base": 13, "until_h": 8}, "words": "armour of force: 13 + dex while unarmoured"},
    "charm person": {"level": 1, "kind": "save", "save": "wis", "range": "here", "adv_if_fighting": True,
                     "cond": {"name": "charmed", "until_h": 1}, "words": "they regard you as a friend for an hour"},
    "hideous laughter": {"level": 1, "kind": "save", "save": "wis", "conc": True, "range": "here",
                         "cond": {"name": "laughing", "also": ["prone", "incapacitated"], "rounds": 10, "save": "wis"},
                         "words": "helpless laughter: prone and incapacitated, a wis save each turn's end"},
    "entangle": {"level": 1, "kind": "save", "save": "str", "conc": True, "range": "sight", "area": True,
                 "cond": {"name": "restrained", "rounds": 10, "escape": "str"},
                 "words": "grasping weeds: restrained until they break free (escape)"},
    "faerie fire": {"level": 1, "kind": "save", "save": "dex", "conc": True, "range": "sight", "area": True,
                    "cond": {"name": "outlined", "rounds": 10}, "words": "outlined in light: attacks on them have advantage"},
    "hold person": {"level": 2, "kind": "save", "save": "wis", "conc": True, "range": "sight",
                    "cond": {"name": "paralyzed", "rounds": 10, "save": "wis"},
                    "words": "paralysed, a wis save at each turn's end to break it"},
    "scorching ray": {"level": 2, "kind": "attack", "attack": "ranged", "dice": "2d6", "dtype": "fire", "rays": 3,
                      "upcast_rays": 1, "range": "sight", "words": "three rays of fire, each its own attack"},
    "shatter": {"level": 2, "kind": "save", "save": "con", "dice": "3d8", "dtype": "thunder", "half": True, "area": True,
                "upcast": "1d8", "range": "sight", "words": "a painful ringing burst"},
    "fireball": {"level": 3, "kind": "save", "save": "dex", "dice": "8d6", "dtype": "fire", "half": True, "area": True,
                 "upcast": "1d6", "range": "sight", "words": "a bead of flame that blooms into an explosion"},
    "lightning bolt": {"level": 3, "kind": "save", "save": "dex", "dice": "8d6", "dtype": "lightning", "half": True,
                       "area": True, "upcast": "1d6", "range": "here", "words": "a line of lightning"},
    "mass healing word": {"level": 3, "kind": "heal", "time": "bonus", "dice": "2d4", "add_mod": True, "upcast": "1d4",
                          "area": True, "range": "here", "target": "ally", "words": "heals everyone not at odds with you here"},
}


# ---- builders for a world's build.py ---------------------------------------------------------------------------------

def mod(score):
    return (int(score) - 10) // 2


def weapon(base, **over):
    """A weapon's state from the table: weapon("longsword", description="...") or weapon("dagger", bonus=1); `kind`
    in over renames it (a hooked sword on a longsword's numbers)."""
    w = WEAPONS[base]
    st = {"weapon": True, "portable": True, "kind": base, "dice": w["dice"], "dtype": w["dtype"],
          "category": w["category"], "properties": list(w["properties"]), "bonus": 0}
    if w.get("versatile"):
        st["versatile"] = w["versatile"]
    if w.get("ranged"):
        st.update({"ranged": True, "ammo": w["ammo"]})
    st.update(over)
    return st


def armor(base, **over):
    """A suit of armour or a shield as a carried thing: armor("chain shirt")."""
    a = dict(ARMOR[base])
    st = {"portable": True, "kind": base, "armor": {"ac": a["ac"], "dex_cap": a.get("dex_cap"), "shield": bool(a.get("shield")),
                                                     "weight": a.get("weight"), "stealth_dis": bool(a.get("stealth_dis"))},
          "bulk": 3 if a.get("weight") == "heavy" else 2 if a.get("weight") == "medium" else 1}
    st.update(over)
    return st


def ac_of(scores, kit=(), unarmored=None, natural=None):
    """The armour class a body with these scores and this kit (states, as weapon() and armor() make) would have."""
    dex = mod(scores.get("dex", 10))
    best = None
    shield = 0
    for st in kit:
        a = st.get("armor") if isinstance(st, dict) else None
        if not a:
            continue
        if a.get("shield"):
            shield = max(shield, int(a.get("ac") or 2) + int(st.get("bonus") or 0))
            continue
        cap = a.get("dex_cap")
        v = int(a["ac"]) + int(st.get("bonus") or 0) + (dex if cap is None else min(dex, int(cap)))
        best = v if best is None else max(best, v)
    if best is None:
        best = (int(natural) if natural is not None else 10) + dex
        if unarmored:
            best += mod(scores.get(unarmored, 10))
    return best + shield


def class_hp(cls, level, con):
    """5e's fixed hit points: the die's maximum at 1st level, its average + 1 after, con modifier every level."""
    die = CLASSES[cls]["die"]
    lvl = max(1, int(level))
    return max(1, die + (lvl - 1) * (die // 2 + 1) + mod(con) * lvl)


def slots_for(cls, level):
    """{level: count} of spell slots a caster of this class and level has; {} for none."""
    c = CLASSES[cls]
    kind = c.get("caster")
    lvl = max(1, int(level))
    if kind == "pact":
        n, at = PACT_SLOTS[min(20, lvl)]
        return {str(at): n}
    if kind == "half":
        lvl = (lvl + 1) // 2
    elif kind != "full":
        return {}
    return {str(i + 1): n for i, n in enumerate(FULL_SLOTS[min(20, lvl)])}


def character(cls, level, scores, spells=None, **over):
    """A body's 5e state for a class and level: level, saving throws, hit points, hit dice, the Attack action's extra
    blows, sneak attack and cunning action for a rogue, unarmoured defence, weapon proficiencies and spellcasting with
    its slots. Lay it over the body's other state (its sheet, its description)."""
    c = CLASSES[cls]
    lvl = max(1, int(level))
    hp = class_hp(cls, lvl, scores.get("con", 10))
    st = {"cls": cls, "level": lvl, "saves": list(c["saves"]), "hp": hp, "max_hp": hp,
          "hit_die": "1d" + str(c["die"]), "hit_dice": lvl, "hit_dice_max": lvl,
          "extra_attacks": sum(1 for x in c.get("extra", []) if lvl >= x), "weapon_prof": list(c["weapons"])}
    if c.get("unarmored"):
        st["unarmored"] = c["unarmored"]
    if c.get("martial_arts"):
        st["martial_arts"] = "1d6" if lvl < 5 else "1d8" if lvl < 11 else "1d10" if lvl < 17 else "1d12"
    if c.get("sneak"):
        st["sneak_attack"] = str((lvl + 1) // 2) + "d6"
    if c.get("cunning") and lvl >= c["cunning"]:
        st["cunning"] = True
    if c.get("cast"):
        slots = slots_for(cls, lvl)
        st["spellcasting"] = {"ability": c["cast"], "spells": list(spells or []), "slots": dict(slots),
                              "slots_max": dict(slots), "pact": c.get("caster") == "pact"}
    st.update(over)
    return st


# ---- the schema and the rules ----------------------------------------------------------------------------------------

ACTIONS = {
    "attack": {"script": "attack", "strikes": True, "targets": "creature", "scope": "here", "duration": 3, "fuel": 600000,
               "doc": "Attack someone here: d20 + modifier + proficiency against their armour class; starts a fight",
               "params": {"with": "the weapon to strike with (default: the first you hold)",
                          "knockout": "true: if this drops them, they are knocked out (stable), not dying"}},
    "shoot": {"script": "shoot", "strikes": True, "targets": "creature", "scope": "sight", "reach": "sight", "duration": 3,
              "fuel": 600000, "doc": "Shoot someone here or one way over with what you hold that fires: an attack roll against "
                                     "their armour class (and their cover); starts a fight"},
    "offhand": {"script": "offhand", "targets": "creature", "scope": "here", "duration": 1, "fuel": 300000,
                "doc": "A bonus blow with a light weapon in your other hand, after you attacked with a light one"},
    "grapple": {"script": "grapple", "targets": "creature", "scope": "here", "duration": 3, "fuel": 600000,
                "doc": "Seize someone (one of your attacks): they save str or dex against 8 + your str + proficiency"},
    "shove": {"script": "shove", "targets": "creature", "scope": "here", "duration": 3, "fuel": 600000,
              "doc": "Shove someone prone (one of your attacks): they save str or dex against 8 + your str + proficiency"},
    "escape": {"script": "escape", "duration": 3, "doc": "Break a grapple or bonds that restrain you: athletics or acrobatics"},
    "dodge": {"script": "dodge", "duration": 3, "doc": "Dodge: attacks on you have disadvantage and you have advantage on dex "
                                                      "saves until your next turn"},
    "brace": {"script": "dodge", "duration": 3, "doc": "Dodge (the same as dodge): attacks on you have disadvantage until your next turn"},
    "dash": {"script": "dash", "duration": 1, "doc": "Dash: another move this turn (leave the place after all)"},
    "disengage": {"script": "disengage", "duration": 1, "doc": "Disengage: leaving the place this turn draws no opportunity attacks"},
    "help": {"script": "help", "targets": "creature", "scope": "here", "duration": 1,
             "doc": "Help an ally: their next attack on someone at odds with you has advantage"},
    "hide": {"script": "hide", "duration": 3, "doc": "Hide: stealth against 15; unseen (advantage on your next attack) until you attack"},
    "stand": {"script": "stand", "duration": 1, "doc": "Stand up from prone (half your move)"},
    "end": {"script": "end_turn", "doc": "End your turn in a fight"},
    "initiative": {"script": "initiative", "duration": 0,
                   "doc": "Roll initiative when a fight starts: give what your own d20 shows, or let the world roll",
                   "params": {"roll": "what your own d20 shows (1 to 20); leave it out and the world rolls for you"}},
    "stats": {"script": "stats", "doc": "Your own numbers: hp, armour class, proficiency, attacks, saves, spells, slots, conditions"},
    "cast": {"script": "cast", "targets": "creature", "self": True, "scope": "sight", "reach": "sight", "duration": 3,
             "listed": "ok",
             "fuel": 600000, "doc": "Cast a spell you know at someone (or yourself)",
             "params": {"spell": "the spell's name (stats lists yours)", "level": "the slot level to spend (default: the spell's own)"}},
    "rest": {"script": "rest", "duration": 3600, "doc": "A short rest, an hour: spend hit dice to heal",
             "params": {"dice": "how many hit dice to spend (default: as many as it takes, up to all)"}},
}

STATE = {"conditions": {}, "exhaustion": 0, "temp_hp": 0, "death_saves": None, "dying": False, "stable": False,
         "fight": None, "initiative": None, "turn": None, "dodging": False, "disengaged": False}


def define(s):
    """The combatant schema with the 5e verbs and keys laid over d20's, the fight's own schema, and the root's settings
    and spell catalogue (the world's own entries win). Idempotent."""
    from packs.d20.pack import COMBATANT_ACTIONS, COMBATANT_STATE
    s.define_schema("combatant", extends="creature",
                    doc="Someone the d20 rules apply to, fighting by D&D 5e: abilities, armour class, hp and death saves, "
                        "conditions, spells, and the verbs of a turn.",
                    state={**COMBATANT_STATE, **STATE}, actions={**COMBATANT_ACTIONS, **ACTIONS},
                    behaviors=[{"script": "thirst", "every": 60, "always": True},
                               {"script": "quench", "every": 60, "idle": True},
                               {"script": "mend", "every": 600, "always": True}])
    s.define_schema("fight", extends="entity", doc="A fight in a place: the initiative order, whose turn, the round.",
                    state={"hidden": True, "order": [], "turn": 0, "round": 1, "foes": {}})
    w = s.world
    root = w.get(w.root_id)
    have = dict(root["state"].get("dnd5e") or {})
    changes = {}
    missing = {k: v for k, v in SETTINGS.items() if k not in have}
    if missing:
        changes["dnd5e"] = {**have, **missing}
    notes = dict(root["state"].get("condition_notes") or {})
    if any(k not in notes for k in CONDITION_NOTES):
        changes["condition_notes"] = {**CONDITION_NOTES, **notes}
    spells = dict(root["state"].get("spells") or {})
    new = {k: v for k, v in SPELLS.items() if k not in spells}
    if new:
        changes["spells"] = {**new, **spells}
    if changes:
        w.patch(w.root_id, changes)


def install_rules(s, root):
    """The fight's rule on the root: turns, the action economy, joining and leaving, rests. Call it after d20's
    install_rules. Idempotent."""
    s.set_rule(root, "fight_rule", kinds=["before_act", "act", "arrived", "fight_next", "slept", "woke", "died", "killed",
                                            "come_round"],
               fuel=1_000_000)
