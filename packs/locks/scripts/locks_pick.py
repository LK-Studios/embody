use("locks")

def check(ctx):
    lk = ctx.target
    if not lk.state.locked:
        return "it is not locked"
    if not lk.state.pick_dc:
        ways = []
        if lk.state.key:
            ways.append("its key")
        if lk.state.code:
            ways.append("its code")
        if lk.state.break_dc:
            ways.append("force (break)")
        return "this lock cannot be picked" + (": it takes " + " or ".join(ways) if ways else "")
    return True

def best_rank(ranks):
    # a lockpick is the trade itself; a quiet hand or a craftsman's comes near it
    best = 0
    for k in ["lockpick", "stealth", "craft"]:
        best = max(best, int(ranks.get(k) or 0))
    return best

def score_mod(attrs, name):
    s = attrs.get(name)
    return 0 if s is None else (int(s) - 10) // 2

def hand(ctx, me):
    # what the picker adds to the d20: wits and the best rank, or, for a body with a sheet (packs/sheet), the sheet's
    # own numbers, read the way its checks read them: the attributes the world's skillbook names for lockpick (Poise
    # when there is no skillbook), averaged when there are two, and the best rank on the sheet
    st = me.state
    sheet = st.sheet
    if not sheet:
        return int(st.wits or 0) + best_rank(st.skills or {})
    entry = {}
    for b in ctx.find(type="skillbook", limit=1):
        entry = (b.state.skills or {}).get("lockpick") or {}
    attrs = sheet.get("attributes") or {}
    mod = score_mod(attrs, entry.get("primary") or "poise")
    if entry.get("secondary"):
        mod = (mod + score_mod(attrs, entry.get("secondary"))) // 2
    return mod + best_rank(sheet.get("skills") or {})

def apply(ctx):
    # quiet while it works: the roll comes when the time is out, and only if you are still there
    lk = ctx.target
    ctx.patch(lk, {"picking": {"who": ctx.actor.id, "at": where_of(ctx)}})
    ctx.log("you set to work on " + lk.name + "; stay here until it gives")

def finish(ctx):
    lk = ctx.get(ctx.target.id)
    if lk is None:
        return
    me = ctx.actor
    at = (lk.state.picking or {}).get("at") if (lk.state.picking or {}).get("who") == me.id else None
    if not lk.state.locked:
        ctx.log(lk.name + " was opened before you were done")
        return
    if at is None or me.parent is None or me.parent.id != at:
        ctx.log("you left " + lk.name + " before it gave")
        return
    held = shut_what(lk)
    mod = hand(ctx, me)
    roll = ctx.rand.roll("1d20")
    total = roll + mod
    dc = int(lk.state.pick_dc)
    if total >= dc:
        ctx.patch(lk, {"locked": False, "picking": None})
        ctx.emit("lock_picked", target=held, reach=1, by=me.id, lock=lk.id, holder=held.id, roll=roll, mod=mod, total=total, dc=dc)
        ctx.log("pick: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": " + lk.name + " gives")
        return
    ctx.patch(lk, {"picking": None})
    ctx.emit("pick_failed", target=held, reach=1, by=me.id, lock=lk.id, holder=held.id, roll=roll, mod=mod, total=total, dc=dc)
    ctx.emit("scene", target=held, reach=1, text="Metal scrapes and clicks at " + lk.name.lower() + ": " + me.name + " is working at it.")
    ctx.log("pick: d20 " + str(roll) + " + " + str(mod) + " = " + str(total) + " vs " + str(dc) + ": it holds, and the room heard you")
