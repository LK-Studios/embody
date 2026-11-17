"""Jobs: work one character gives and another takes, done by deeds the world sees, paid by the world's rules, and
given again when it is needed again.

A world names it after d20 in its manifest (`"requires": ["d20", "jobs"]`; pay in standing and deeds goes through
d20's factions and growth). The pack binds four verbs on every body (`creature`, read and written back merged, so a
re-run is idempotent) and defines the `job` schema. A world installs the rule on its root with
`install_rules(s, root, dusk="dusk", dawn="dawn")` (the event kinds that start its night and its day) in its
populate and its upgrade.

A job is a thing in the world. Where it lies decides how it reaches people:
- a posting: a job lying in a place (a notice nailed up, a chalked slate) is open to anyone who stands there;
- a promise: a job its giver carries (hidden, on their body) reaches someone only when the giver offers it to them,
  with `offer_job` (the giver acts on the person, params `job`). A mind giver says it in words, then offers it, so the
  contract exists; it never has to judge whether the work was done.

Its state:
- `giver`: the name or id of the one it is for (a person, or a faction's leader). Pay comes from them by default.
- `terms`: the line a taker reads: what to do, and what it pays.
- `gate`: who may take it. {"standing": {faction: min}} (d20 standing with that faction, at or above min),
  {"faction": name} (one of theirs), {"skill": {skill: rank}} (a sheet rank at or above). Empty: anyone. A refusal
  names what is missing, never a number the taker cannot read.
- `done`: what must happen, matched by the rule against the world's own events, so done is the log's call, never
  anyone's word: {"kind": "killed" | "downed" | "beast_driven_off" | "beast_turned_back" | "beast_died" | "given" |
  "arrived", or a list of them, "by_taker": true, the default (the taker's own deed: `by` on killed, downed and the
  beasts pack's driven off and turned back, where the pack in `hunters` is what must match; a beast_died names no
  hand, so it counts only with by_taker false; a given is always the taker's, to the giver unless `target` names
  someone; an arrived is the taker's), "species": a beast's species, "type": a schema,
  "target": a name, "item": a name or kind (given), "at": a place's name (where it happened), "count": how many
  (default 1)}. Anything left out matches anything.
- `window`: {"night": true} (counts only between the world's dusk and dawn), {"days": n} (fails n world days after
  it was taken).
- `pay`: {"items": [{"kind": a name or kind, "count": n, "from": a name (default the giver)}], "standing": n (with
  the giver's faction), "deed": {"skill": name, "amount": n} (d20 growth, within its deed caps)}. Pay is the floor:
  a giver may add more by hand.
- `repeat`: "once" (done once, then closed for all), "reopen" (closed after each done until a rule reopens it),
  "always" (stays open: a standing bounty), or {"every_days": n} (open again n world days after each done). `slots`:
  how many may hold it at once (default 1). Whoever still holds a closed job may still finish it.
- `toward`: {"entity": a name or id, "key": a state key, "add": n (default 1)}: each done adds to that counter, so a
  world's larger arc can wait on the work.
- written by play, secret (the owner and authors inspect them): `holders` {taker id: {since, count, until}},
  `offers` {person id: since}, `done_by` {taker id: times}; and `open`, `done_count`.

Verbs every body has:
- `jobs`: the jobs you could take here (postings where you stand, promises offered to you), each with its terms and,
  when you cannot take it, why not; and the ones you hold, with how far along.
- `take_job` {"job"}: take one of them. Checked against the gate, the slots and whether it is open.
- `drop_job` {"job"}: give it up. It counts as failed.
- `offer_job` {"job"}, done to a person here: offer a job you give (you are its giver, or you carry it).

A world rule reopens a job with `use("jobs")` then `reopen(ctx, job, why)`: a goat taken in the night reopens the
hunt. Events (target the taker, reach 1, with `job` and `giver`): `job_offered`, `job_taken`, `job_done`,
`job_failed` {why: dropped, window, dead}, `job_paid` {items, standing, deed, short (what the giver lacked)},
`job_reopened` (target the job).

What a world does not need: no completion code, no pay code. What it builds: its jobs (where they lie or who carries
them), its givers' minds and lines, and the rules that reopen a job when the need comes back.
"""

PACK = {"name": "jobs", "description": "Work one character gives and another takes: done by deeds the world's log "
                                       "sees, paid by the world's rules, given again when it is needed again."}

RULES = [
    {"id": "jobs", "date": "2026-11-17",
     "was": "Work for someone was a promise in words; nothing kept it, checked it or paid it.",
     "now": "A job is a thing in the world: a posting lying where people stand, or a promise its giver carries and "
            "offers to someone (offer_job). jobs lists what you could take here, and why not; take_job takes one, "
            "drop_job gives it up. The world checks the work from its own events (a beast killed, a thing handed "
            "over, a place reached, at night if the job says so) and pays what the job names (things, standing with "
            "the giver's people, growth). Some jobs come back when the need does.",
     "recheck": ["promises you made or hold in notes", "watch filters: job_offered, job_done, job_paid, job_failed"],
     "guide": ["player", "mind"]},
]

BODY_ACTIONS = {
    "jobs": {"script": "jobs_list", "doc": "The jobs you could take here and why not, and the jobs you hold"},
    "take_job": {"script": "jobs_take", "params": {"job": "the job's name, as jobs lists it"},
                 "doc": "Take a job posted here or offered to you"},
    "drop_job": {"script": "jobs_drop", "params": {"job": "the job's name"}, "doc": "Give up a job you hold"},
    "offer_job": {"script": "jobs_offer", "targets": "creature", "scope": "here", "listed": "ok",
                  "params": {"job": "the job's name"}, "doc": "Offer a job you give to someone here"},
}

JOB_STATE = {"portable": False, "giver": None, "terms": "", "gate": {}, "done": {}, "window": {}, "pay": {},
             "repeat": "once", "slots": 1, "toward": None, "open": True, "done_count": 0,
             "holders": {}, "offers": {}, "done_by": {}, "secret": ["holders", "offers", "done_by"]}


def define(s):
    """The job schema, and jobs, take_job, drop_job and offer_job on every body. Idempotent."""
    row = s.world.schema("creature")
    actions = dict(row["actions"])
    actions.update(BODY_ACTIONS)
    s.define_schema("creature", extends=row["extends"], doc=row["doc"], state=row["state"], actions=actions,
                    listeners=row["listeners"], behaviors=row["behaviors"], senses=row["senses"], space=row["space"])
    s.define_schema("job", extends="thing",
                    doc="Work someone gives: its terms, who may take it, what counts as done, what it pays, whether "
                        "it comes back. A posting where it lies; a promise when its giver carries it.",
                    state=JOB_STATE)


DONE_KINDS = ["killed", "downed", "beast_died", "beast_driven_off", "beast_turned_back", "given", "arrived", "died"]


def install_rules(s, root, dusk="dusk", dawn="dawn"):
    """The jobs rule on the root: the done kinds, the taker's death, the world's dusk and dawn (for night jobs), and
    the pack's own job_due and job_reopen. Idempotent."""
    kinds = DONE_KINDS + [k for k in (dusk, dawn) if k] + ["job_due", "job_reopen"]
    r = s.world.need(s._resolve(root))
    cur = dict(r["state"].get("jobs") or {})
    cur.update({"dusk": dusk, "dawn": dawn})
    s.patch(root, {"jobs": cur})
    s.set_rule(root, "jobs_rule", kinds=kinds, fuel=400_000)
