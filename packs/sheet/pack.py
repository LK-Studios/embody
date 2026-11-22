"""Sheets: twelve attributes, skills ranked 0 to 15 that grow with use, and grants. Opt-in, on top of d20: a world names
it after d20 in its manifest (`"requires": ["d20", "sheet"]`), and only a body with a `sheet` rolls by it. Every other
body rolls d20 + body, wits or will + a skill, exactly as before.

The numbers, so a narrator can explain a roll:

- A body's `sheet` is `{"attributes": {...}, "skills": {...}, "xp": {...}}`. The twelve attributes are force, poise,
  endurance, acuity, cognition, discipline, tenacity, comprehension, projection, coherence, persistence and attunement,
  each a score of 1 to 20 (missing: 10). The modifier is (score - 10) // 2, so -4 to +5.
- A skill has a rank of 0 to 15, added whole. The world's skillbook (one `skillbook` entity, its `skills` keyed by name)
  gives each skill a `primary` attribute and an optional `secondary` one (the two modifiers averaged, rounded down), a
  `scope` in words and `related` skills. A related skill lends its rank // 3 when that is more than the skill's own;
  related ranks never stack. A skill the skillbook does not name rolls untrained on acuity (`untrained` in the rules).
  An author adds a skill by patching the skillbook: no code.
- A check is d20 + modifier + rank + grants against a difficulty. Wounded costs 2, thirsty costs 2, as for everyone.
  A natural 1 or 20 is just a number.
- Grants: `grants` on a body, a list of {source, bonus, skill, place, until, uses, condition}. Each one for this skill
  (none: any) in this place (none: anywhere) before `until` (world t) adds its bonus; from one source only the largest
  counts. `uses` spends one a roll and the grant goes at 0; `condition` is the narrator's words, carried, not checked.
  A sheet body's `aid` (a familiar's hand) is a grant for one use. A negative bonus is an injury.
- Weapons name their skill (`skill` on the weapon: "short blades"); one that names none rolls blade, aim or brawl.
- Progression: only a difficulty the world set teaches. A find, a lock, a hazard, tend's 12, a world
  verb's own dc and every opposed roll (a blow, a shot, parley, threaten, a sleeper searched) teach; `check` with a dc
  the caller chose never does. The roll it needed is the dc less the body's natural bonus (no grants, no conditions):
  needed 1 to 7 earns 0, 8 to 12 earns 1, 13 to 16 earns 2, 17 to 20 earns 3, and nothing past 20 (out of reach) or
  below 1. A success doubles it. Rank r to r + 1 costs 10 x (r + 1), or `rank_costs`[r] when the world sets a list
  (the Reach: 6 x 1.4^r). At most 3 teaching rolls a skill, a target, a world day. Every award is a `learned` event on the body (reach 0: its own feed), with the skill, what it needed,
  what it earned, its xp and rank; the event log is the ledger. Only the world's rules teach and write a sheet or
  skills: a guest's script, a frame's code and a verb programmed on one thing never do (refused, and learn under
  them teaches nothing).
- Teachers: with `self_taught` on the root's `sheet_rules` (none by default), use raises a skill only to that rank;
  past it, use banks experience up to the next rank (`learned` says `teacher`: true when it is full) and a teacher
  turns it into the rank. A teacher is any body with `teaches`: {skill: {up_to, price, every_days}}. `train` (d20,
  on the teacher, params `skill`) spends the experience, pays the `price` (`water` from your own, any other key a
  stack of that kind you hold, such as ember, handed to the teacher), and emits `trained`; `every_days` keeps a
  teacher to one lesson a student in that many world days. A teacher teaches from rank 1: below self_taught a lesson
  is experience (`lesson_xp`; none: a third of the rank's cost). A teacher teaches only below its own rank in the skill
  (a sheet's rank, or a flat skill), up to its `up_to`, and with `teach_skill` set only with rank 1 or more in that
  skill too. A world's own verbs teach with `learn(ctx, who, skill, dc, success, against)` from d20's common.
- Practice: d20's `practice` (an hour alone, params `skill`) rolls against `practice_dc` by rank (a list; none: 10 +
  rank), earns by the same bands, at least 1, and at most a third of a rank's cost comes from practice.
- Deeds: `deed(ctx, who, skill, amount, why)` from d20's common, for a world's own scripts (the world decides which
  deeds count): at most a third of a rank's cost from deeds, apart from practice's third. Each is a learned event with
  `source` deed and the why. Every learned event says its source: use, practice, deed or lesson.
- Attributes grow with `attr_cap` set (none by default): each point a skill earns counts toward its primary
  attribute, score s to s + 1 costs attr_cost_base x attr_cost_x ^ (s - 10) (40 x 1.6), up to attr_cap; max_score
  stays for boons. A rise is a `grew` event.
- `grant_cap` (none by default): all grants together add at most that to one roll.
- Every number above lives on the world root as `sheet_rules` (the pack writes the defaults once; the world's DM tunes
  them there): earn, success_x, rank_cost, max_rank, per_target_day, related_div, untrained, min_score, max_score,
  self_taught, rank_costs, practice_dc, lesson_xp, teach_skill, attr_cap, attr_cost_base, attr_cost_x, grant_cap.
- `perceive` shows a sheet as its attributes and the skills that have a rank (and, on your own card, the xp toward the
  next). guide('skills') has the skillbook and the rules.
- A d20 body moves across with `to_sheet(state)`: body to force, poise, endurance; wits to acuity, cognition,
  comprehension; will to discipline, tenacity, projection (each 10 + 2 x the stat); coherence, persistence and
  attunement at 10; skills keep their ranks. Over the default skillbook it rolls exactly the bonus it rolled before.
  body, wits and will stay on the body for rules that still read them raw.
"""

PACK = {"name": "sheet", "description": "Twelve attributes, skills that grow with use, and grants: an opt-in character sheet on top of d20."}

RULES = [
    {"id": "practice", "date": "2026-11-16",
     "was": "Experience came only from use against the world's difficulties, and from a teacher past self_taught; "
            "attributes never grew and grants had no total cap.",
     "now": "A world may set rank_costs (a cost per rank), and practice (an hour alone) and deeds the world rewards each "
            "give at most a third of a rank. Teachers teach from rank 1: below self_taught a lesson is experience; a "
            "teacher teaches only below its own rank (and, where the world names it, needs teaching). With attr_cap set "
            "a skill's experience slowly raises its primary attribute. With grant_cap set all grants together add at "
            "most that. Every learned event says its source.",
     "recheck": ["plans that count experience by the old costs", "notes on what a teacher can teach"],
     "guide": ["player", "mind"]},
    {"id": "teachers", "date": "2026-11-15",
     "was": "Use raised a skill's rank all the way to max_rank, and a world's own verbs could write a sheet.",
     "now": "A world may set `self_taught` in its sheet_rules: use raises a skill to that rank only, then banks "
            "experience for the next one, and a teacher (a body that `teaches` the skill) turns it into the rank with "
            "train, for a price. Only the world's rules write a sheet or skills: a guest's script, a frame and a verb "
            "programmed on one thing are refused.",
     "recheck": ["plans that grind one skill past its self-taught rank", "notes that write your own skills"],
     "guide": ["player", "mind"]},
    {"id": "sheet", "date": "2026-11-14",
     "was": "Every body rolled d20 + body, wits or will + a skill of 0 to 3.",
     "now": "A body with a sheet rolls d20 + an attribute modifier ((score - 10) // 2, two attributes averaged down) + a "
            "skill rank (0 to 15) + its grants. Its skills grow with use, only against difficulties the world sets (a "
            "find, a lock, a hazard, an opposed roll; never a check whose dc you chose), and every award is a learned "
            "event. Bodies without a sheet roll as before. guide('skills') has the skillbook and the numbers.",
     "recheck": ["notes that count your stats or skills", "plans that repeat a check to train it"],
     "guide": ["player", "mind"]},
]

ATTRIBUTES = ["force", "poise", "endurance", "acuity", "cognition", "discipline", "tenacity", "comprehension",
              "projection", "coherence", "persistence", "attunement"]

# what each d20 stat becomes on a sheet: three attributes each, at 10 + 2 x the stat
FROM_STAT = {"body": ["force", "poise", "endurance"], "wits": ["acuity", "cognition", "comprehension"],
             "will": ["discipline", "tenacity", "projection"]}

# the d20 ten (and dodge, a shot's defence) as the skillbook's first entries, each on attributes of the stat it used
# to lean on, so a converted body rolls what it rolled before
CATALOGUE = {
    "blade": {"primary": "force", "secondary": "poise", "scope": "fighting with a blade", "related": []},
    "brawl": {"primary": "force", "secondary": "endurance", "scope": "fists, grappling, a fight with nothing in hand", "related": []},
    "climb": {"primary": "poise", "secondary": "force", "scope": "walls, cliffs, ropes", "related": []},
    "stealth": {"primary": "acuity", "secondary": None, "scope": "going unseen and unheard, a light hand", "related": []},
    "survival": {"primary": "comprehension", "secondary": "acuity", "scope": "water, weather, tracks, binding a wound", "related": []},
    "lore": {"primary": "comprehension", "secondary": "cognition", "scope": "what is known: history, the glass, old signs", "related": []},
    "lockpick": {"primary": "cognition", "secondary": "acuity", "scope": "locks and the tools for them", "related": ["stealth"]},
    "aim": {"primary": "acuity", "secondary": "cognition", "scope": "bows, slings, anything that flies", "related": []},
    "dodge": {"primary": "acuity", "secondary": None, "scope": "getting out of the way of a shot", "related": []},
    "parley": {"primary": "projection", "secondary": "discipline", "scope": "talking terms, persuading", "related": []},
    "resolve": {"primary": "tenacity", "secondary": "discipline", "scope": "holding firm under threat or fear", "related": []},
}

SHEET_RULES = {"earn": [[7, 0], [12, 1], [16, 2], [20, 3]], "success_x": 2, "rank_cost": 10, "max_rank": 15,
               "per_target_day": 3, "related_div": 3, "untrained": "acuity", "min_score": 1, "max_score": 20,
               "self_taught": None, "rank_costs": None, "practice_dc": None, "lesson_xp": None, "teach_skill": None,
               "attr_cap": None, "attr_cost_base": 40, "attr_cost_x": 1.6, "grant_cap": None}


def to_sheet(state: dict) -> dict:
    """A d20 body's state as a sheet: each stat to its three attributes at 10 + 2 x the stat, the rest at 10, the skills'
    ranks carried over. Deterministic, so the same body always converts the same."""
    attrs = {a: 10 for a in ATTRIBUTES}
    for stat, names in FROM_STAT.items():
        for a in names:
            attrs[a] = 10 + 2 * int(state.get(stat) or 0)
    return {"attributes": attrs, "skills": {k: int(v) for k, v in (state.get("skills") or {}).items() if int(v or 0) > 0},
            "xp": {}}


def define(s):
    """The skillbook schema; the world's skillbook (made once, under the root, with the d20 ten) and the default
    `sheet_rules` on the root, key by key, so a DM's own numbers stay. Idempotent."""
    s.define_schema("skillbook", extends="entity",
                    doc="The world's skills: {name: {primary, secondary, scope, related}}. Bodies with a sheet roll by it.",
                    state={"hidden": True, "skills": {}})
    w = s.world
    root = w.get(w.root_id)
    rules = dict(root["state"].get("sheet_rules") or {})
    missing = {k: v for k, v in SHEET_RULES.items() if k not in rules}
    if missing:
        w.patch(w.root_id, {"sheet_rules": {**rules, **missing}})
    if not w.find(type="skillbook", limit=1):
        w.spawn("skillbook", w.root_id, "Skillbook", state={"skills": CATALOGUE})
