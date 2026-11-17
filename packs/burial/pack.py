"""Burial: the dead decay by world time, and the living bury them where a world keeps its dead.

A world names it after d20 in its manifest (`"requires": ["d20", "burial"]`; exhuming moves standing with d20's
factions). The pack binds two verbs on every body (`creature`, read and written back merged, so a re-run is
idempotent) and defines the `grave` schema. A world installs the decay rule on its root with
`install_rules(s, root)`, in its populate and its upgrade; it stamps the dead already lying there on its first sweep.

Decay. When a body dies (`killed`, `died`, `beast_died`) the rule writes `died_at` (world time) and `decay: "fresh"`
on it and schedules the turns: `foul` a world day after death, `bones` seven days after (a beast's bones come at
three, as its carcass does). The stage lengths are the world's: root `burial.decay` {"foul": s, "bones": s} for
people, `burial.decay_beast` for beasts, and a body's own `decay_after` wins over both. A foul body's description
gains a line (it smells, the flies have found it) and a body that was food (a beasts carcass) is carrion only: its
meat is gone. Bones replace the description. Root `burial.notes` {"foul": ..., "bones": ..., "bones_beast": ...}
rewords the lines. Each turn emits `decayed` {body, stage}; a body's condition carries `decay` (fresh, foul, bones).
A daily sweep (`burial_sweep`, every world day) stamps any dead body a rule never heard die (an author's patch, a
pack that emits nothing) and catches up any turn a timer missed. Revival is a host's repair: clear `died_at`,
`decay` and `description_alive` (the description it had before it turned) with the rest.

Burying. `bury` is anyone's verb, done to a dead body here, and works only where the place, or a thing in it, has
`burial_ground: True` (as `water_source` marks water). It takes a quarter of a world hour of digging, and 2 water
from a body that keeps water (root `burial.water`). Params: `words` (what is said over it, optional, at most 200
characters, root `burial.words_max`; no ids and no tool calls, as `say` refuses them), `marker` (a portable thing
you hold, by name or id, set at its head). When the time is out, if the digger and the body are both still there,
the body leaves play: it goes into a new `grave` in the place, hidden, with what it carried, and the grave keeps
`lies` (the name), `buried_by`, `buried_at` (world time) and the `words`. A body whose seat is still held (a player
or a mind sits in it: the dead still perceive) is buried only once that seat gives its leave with `let_bury` (a verb
the dead may use: unlisted, and named in the dead's "you are dead" hint) or `burial.seat_wait` world seconds after
death (default a world day). Beasts are buried the same.

The grave's verbs:
- `mark` {"item"}: set a portable thing you hold at its head as its marker. The marker stays (`attached`, no longer
  portable) and is read and inspected where the grave is. One marker a grave.
- `inscribe` {"text"}: cut a line into its marker (or into the grave's own headboard when it has none), at most 120
  characters (`burial.inscription_max`), with say's filter. One inscription; only whoever cut it may cut it again,
  unless the root says `burial.inscribe_over: true`. `read` (village) reads it.
- `adorn` {"text"}: add a short line to its description ("a ring of white stones"), at most 80 characters
  (`burial.adorn_line_max`), dated in the grave's state, at most 8 a grave (`burial.adorn_max`); the oldest stay and
  a full grave refuses more.
- `exhume`: a quarter of an hour of digging; the body comes back out where the grave was, the marker lies loose
  beside it, the grave is gone. It costs the digger `burial.exhume_standing` (default -2) with the dead one's faction
  (d20 standing, so enough of it outlaws), and a world that names it a crime (`burial.exhume_crime: true`) gets
  `crime: true` on the event for its own rules to answer.

Events (target the grave, reach 1, so the place and a watch on it see them, and a root rule hears them): `buried`
{by, grave, place, body, words}, `grave_marked` {by, grave, place, marker}, `inscribed` {by, grave, place, text},
`adorned` {by, grave, place, text}, `exhumed` {by, grave, place, body, crime}, and on the body `decayed` {body,
stage} and `left_to_bury` {body} when a seat gives its leave. (`marked` is the engine's own, for marks on a body's
looks.) Every verb is callable by a routine the same as by a seat: a world's undertaker acts them as anyone does.

What a world does not need: no decay ticks of its own, no grave code. What it builds: its burial grounds (the flag
on a place or a thing), who digs, and its customs (rules that answer `buried` and `exhumed`).
"""

PACK = {"name": "burial", "description": "The dead decay by world time; the living bury them in burial grounds, "
                                         "mark, inscribe and adorn graves, and may exhume them at a cost."}

RULES = [
    {"id": "burial", "date": "2026-11-17",
     "was": "A dead body lay where it fell, forever, unchanged.",
     "now": "The dead decay by world time: fresh, then foul after a world day (a carcass's meat is carrion then), then "
            "bones (seven days for people, three for beasts, or as the world sets). Where a place or a thing in it is a "
            "burial ground, anyone may bury a dead body there (bury, params words and marker): it goes into a grave that "
            "keeps who lies there, who buried them and the words. A grave takes mark, inscribe, adorn and exhume "
            "(which costs standing with the dead one's people). A dead seat may let_bury to give its leave; else it "
            "waits a world day.",
     "recheck": ["plans and notes about the dead lying somewhere", "watch filters: buried, exhumed, decayed"],
     "guide": ["player", "mind"]},
]

BODY_ACTIONS = {
    "bury": {"script": "burial_bury", "targets": "creature", "scope": "here", "listed": "ok", "duration": 900,
             "doc": "Bury a dead body here, where the place or a thing in it is a burial ground: a quarter hour of "
                    "digging; it lies in a grave after",
             "params": {"words": "what you say over it (optional)", "marker": "a thing you hold to set at its head (optional)"}},
    "let_bury": {"script": "burial_let", "dead_ok": True, "hidden": True,
                 "doc": "(the dead) Give your leave: the living may bury your body now"},
}

GRAVE_ACTIONS = {
    "mark": {"script": "burial_mark", "duration": 30, "params": {"item": "a thing you hold to set at its head"},
             "doc": "Set a thing you hold at its head as its marker"},
    "inscribe": {"script": "burial_inscribe", "duration": 60, "params": {"text": "the line to cut (short)"},
                 "doc": "Cut a line into its marker, or its headboard"},
    "adorn": {"script": "burial_adorn", "duration": 20, "params": {"text": "what you leave on it, in a few words"},
              "doc": "Leave something on it: a line added to how it looks"},
    "exhume": {"script": "burial_exhume", "duration": 900,
               "doc": "Dig the body up again: a quarter hour, and the dead one's people hold it against you"},
}


def define(s):
    """The grave schema, and bury and let_bury on every body. Idempotent."""
    row = s.world.schema("creature")
    actions = dict(row["actions"])
    actions.update(BODY_ACTIONS)
    s.define_schema("creature", extends=row["extends"], doc=row["doc"], state=row["state"], actions=actions,
                    listeners=row["listeners"], behaviors=row["behaviors"], senses=row["senses"], space=row["space"])
    s.define_schema("grave", extends="thing",
                    doc="Where someone lies buried: who, who buried them, when, the words; a marker, an inscription, "
                        "what was left on it.",
                    state={"portable": False, "lies": None, "buried_by": None, "buried_at": None, "words": None,
                           "marker": None, "inscription": None, "inscribed_by": None, "adornments": [],
                           "remains": None, "secret": ["remains", "inscribed_by"],
                           "description": "A mound of turned earth."},
                    actions=GRAVE_ACTIONS)


SWEEP = 86400  # a world day


def install_rules(s, root, sweep=SWEEP):
    """The decay rule on the root, and its daily sweep (scheduled once: a re-run leaves the timer as it is). The first
    sweep comes a world minute after install and stamps the dead already lying in the world. Idempotent."""
    s.set_rule(root, "burial_rule", kinds=["killed", "died", "beast_died", "burial_decay", "burial_sweep"],
               fuel=400_000)
    if not (s.world.need(s._resolve(root))["state"].get("burial_sweep")):
        s.patch(root, {"burial_sweep": sweep})
        s.schedule(60, "burial_sweep", entity=root, every=sweep)
