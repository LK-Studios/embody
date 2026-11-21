use("common")
def on(ctx, event):
    # standing moves on deeds: strike a member and the faction remembers; at -4 they come for you
    k = event.kind
    t = ctx.get(event.target) if event.target else None
    by = ctx.get(event.payload.get("by")) if event.payload.get("by") else None
    if k == "dishonor":
        who = ctx.get(event.target)
        if who is None:
            return
        for f in ctx.find(type="faction", limit=20):
            shift_standing(ctx, who, f, -2, "dishonor")
        return
    if t is None or by is None or by.id == t.id:
        return
    if k == "given" and came_back(ctx, event.payload.get("item"), t):
        return
    f = faction_of(ctx, t)
    if f is None or by.state.faction == f.name:
        return
    # one who keeps their side secret does not give it away: the faction counts the deed without naming itself
    quiet = "faction" in (t.state.secret or [])
    if k == "hit":
        if struck_back(ctx, by, t):
            return  # defence: the faction counts who started the fight, not every blow in it
        shift_standing(ctx, by, f, -2, "struck " + t.name, quiet, True)  # a blow: time forgives it
    elif k == "killed":
        shift_standing(ctx, by, f, -5, "killed " + t.name, quiet)
    elif k == "cowed":
        shift_standing(ctx, by, f, -1, "threatened " + t.name, quiet)
    elif k == "agreed":
        if counted_today(ctx, f, "agreed", by, t):
            return
        shift_standing(ctx, by, f, 2, "terms with " + t.name, quiet)
    elif k == "given":
        # a gift is something they keep: a trade (the thing is gone by now) or a return (they gave it first) is not one
        item = ctx.get(event.payload.get("item"))
        if item is None or item.parent is None or item.parent.id != t.id or item.state.given_before_by == t.id:
            return
        if counted_today(ctx, f, "given", by, t):
            return
        shift_standing(ctx, by, f, 1, "a gift to " + t.name, quiet)
        lent = dict(f.state.lent or {})
        lent[item.id] = {"by": by.id, "quiet": quiet}
        keep_secret(ctx, f, {"lent": dict(list(lent.items())[-50:])})

def struck_back(ctx, by, t):
    # a blow at someone who struck you first, while that grudge holds (grudge_for), is defence and costs no standing.
    # Two sides with no mind used to feed each other -2 a blow for good, each strike back outlawing the striker.
    st = by.state
    return st.attacked_by == t.id and st.attacked_at is not None and ctx.t - float(st.attacked_at) < grudge_for(ctx)

def counted_today(ctx, f, kind, by, t):
    # terms or a gift buys standing once a pair a world day: the same offer to the same member ten times is one
    # deed, not ten (a playtest farmed +29 from parley). Kept secret on the faction; earlier days fall away.
    day = int(ctx.t // ctx.day_seconds())
    key = kind + ":" + by.id + ":" + t.id
    seen = dict(f.state.courted or {})
    if seen.get(key) == day:
        return True
    for k in list(seen):
        if seen[k] != day:
            seen[k] = None
    seen[key] = day
    keep_secret(ctx, f, {"courted": seen})
    return False

def came_back(ctx, item_id, giver):
    # a gift handed back to the one who gave it was a loan: the standing it bought goes again
    for f in ctx.find(type="faction", limit=20):
        lent = dict(f.state.lent or {})
        rec = lent.get(item_id)
        if rec and rec.get("by") == giver.id:
            lent.pop(item_id)
            keep_secret(ctx, f, {"lent": lent})
            shift_standing(ctx, giver, f, -1, "lent, not given: it came back", rec.get("quiet"))
            return True
    return False
