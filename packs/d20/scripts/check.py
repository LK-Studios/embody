use("common")
def again_after(ctx):
    # world seconds before a body may try the same skill in the same place again (root `check_again_after`, default
    # a world hour): a check rolled until it lands would find every hidden thing at any dc
    v = ctx.root().state.check_again_after
    return float(v) if v is not None else ctx.day_seconds() / 24

def check(ctx):
    p = ctx.params or {}
    skill = str(p.get("skill") or "")
    here = ctx.actor.parent
    if not skill or here is None:
        return True
    last = (ctx.actor.state.tried or {}).get(here.id + "|" + skill)
    if last is not None and ctx.t - float(last) < again_after(ctx):
        mins = int((again_after(ctx) - (ctx.t - float(last))) // 60) + 1
        return ("you tried " + skill + " here a short while ago, and it gave what it will for now: try again in about "
                + str(mins) + " world minutes, or try another way")
    return True

def apply(ctx):
    # d20 + stat + skill against a difficulty; everyone near sees the numbers
    p = ctx.params or {}
    skill = str(p.get("skill") or "")
    dc = int(p.get("dc") or 12)
    roll = ctx.rand.roll("1d20")
    mod = bonus(ctx.actor, skill, ctx)  # a dc the caller chose teaches nothing: no learn here
    here = ctx.actor.parent
    aid = take_aid(ctx, ctx.actor, skill, here)
    if aid is not None:
        mod = mod + int(aid.get("bonus") or 0)
    total = roll + mod
    ok = total >= dc
    if skill and here is not None:
        keep = {}
        for k, t in (ctx.actor.state.tried or {}).items():
            keep[k] = t if ctx.t - float(t) < again_after(ctx) else None  # a patch merges; None deletes
        keep[here.id + "|" + skill] = ctx.t
        ctx.patch(ctx.actor, {"tried": keep})
    # a skill nobody here has heard of is still a roll, an untrained one on wits, and the result says so plainly
    untrained = bool(skill) and not known_skill(ctx, ctx.actor, skill)
    note = None
    if untrained:
        note = "no skill '" + skill + "' here: an untrained roll on wits (skills: " + ", ".join(sorted(SKILLS)) + ")"
        if ctx.actor.state.sheet:
            note = "no skill '" + skill + "' in this world's skillbook: an untrained roll on " + sheet_rules(ctx)["untrained"] + " (guide('skills') lists them)"
    ctx.emit("checked", target=ctx.actor, reach=1, by=ctx.actor.id, place=here.id if here is not None else None,
             skill=skill, roll=roll, mod=mod, total=total, dc=dc, success=ok, margin=total - dc, untrained=untrained, aid=aid)
    helped = " (+" + str(aid.get("bonus") or 0) + ": " + str(aid.get("why") or "a hand from someone") + ")" if aid is not None else ""
    ctx.log(skill + ": d20 " + str(roll) + " + " + str(mod) + helped + " = " + str(total) + " vs " + str(dc) + (" pass" if ok else " fail") + (" (" + note + ")" if note else ""))
    out = {"roll": roll, "mod": mod, "total": total, "dc": dc, "success": ok}
    if aid is not None:
        out["aid"] = aid
    if note:
        out["untrained"] = True
        out["note"] = note
    return out
