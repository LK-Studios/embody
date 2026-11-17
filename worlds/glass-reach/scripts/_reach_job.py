# Jobs (Nate 2026-11-17: "a job is a questline or goal that can be repeated ... a contract between two characters that
# must be fulfilled ... the player fulfilling a job plays a role in some bigger thing"). The Reach's own until the
# engine has a jobs pack. A job lives on a thing (`job` in its state): who gives it, who may take it, what counts as
# done and when, and what it pays. Takers sign on at the thing while the giver is there; the world's record, not
# anyone's word, says when it is done. One job's data, all of it on the thing:
#   giver (a body id), faction + min_standing (the gate), species (the beasts it is about), trouble (event kinds about
#   them that open it again), done_on (event kinds by the taker that finish it), window ("night": only between dusk and
#   dawn), slots, lapse_days, pay {standing, skill, deed}, lines (what the world says), and its own
#   record: open, takers [{who, t}], ledger [{who, name, day, how}]. Lists, not dicts: a patch merges a dict, so a
#   taker taken off a dict would stay.
use("common")

def job_of(thing):
    return dict(thing.state.job or {})

def taker_ids(j):
    return [d.get("who") for d in (j.get("takers") or [])]

def faction_named(ctx, name):
    for f in ctx.find(type="faction", limit=20):
        if f.name == name:
            return f
    return None

def line(j, key, who=None, giver=None):
    text = (j.get("lines") or {}).get(key) or ""
    if who is not None:
        text = text.replace("{who}", who.name)
    if giver is not None:
        text = text.replace("{giver}", giver.name)
    return text

def why_not(ctx, thing, who):
    # the honest reason this body cannot take the job now, and what would work; None when it can
    j = job_of(thing)
    giver = ctx.get(j.get("giver")) if j.get("giver") else None
    if giver is None or giver.state.dead:
        return "nobody gives this work now"
    if who.id == giver.id:
        return "it is yours to give, not to take"
    if who.state.beast or who.state.dead or who.state.down:
        return "you are in no state to take work"
    takers = taker_ids(j)
    if who.id in takers:
        return "you have it already. " + line(j, "terms", who, giver)
    if not j.get("open"):
        return line(j, "closed", who, giver) or "there is no call for it now"
    if giver.parent is None or who.parent is None or giver.parent.id != who.parent.id:
        return line(j, "away", who, giver) or (giver.name + " gives this work in person: find them")
    if giver.state.down or giver.state.asleep:
        return giver.name + " is in no state to give work just now"
    if len(takers) >= int(j.get("slots") or 1):
        return "enough have it already; it opens again if the trouble comes back"
    f = faction_named(ctx, j.get("faction")) if j.get("faction") else None
    if f is not None and who.state.faction != f.name:
        if (f.state.hostile or {}).get(who.id) or standing(ctx, who, f) < int(j.get("min_standing") or 0):
            return line(j, "refused", who, giver) + " (Your standing with " + f.name + " is too low for this work: " \
                   "terms with them, or a gift one of them keeps, raise it.)"
    return None

def night(ctx):
    # the Reach keeps day and night on its story (`wild_night`, set at dusk, cleared at dawn: scripts/reach_wild.py)
    st = ctx.find(type="story", limit=1)
    return bool(st and st[0].state.wild_night)

def in_window(ctx, j):
    w = j.get("window")
    if w == "night":
        return night(ctx)
    return True

def of_species(ctx, eid, species):
    b = ctx.get(eid) if eid else None
    return b is not None and b.state.species == species
