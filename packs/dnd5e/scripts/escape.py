use("common")
use("five")
# Break a hold or bonds: athletics (str) or acrobatics (dex), the better, against the number the hold set.

def holds(ctx, me):
    out = []
    for k, e in conds(ctx, me).items():
        if (k == "grappled" or k == "restrained") and e.get("escape"):
            out.append([k, e])
    return out

def check(ctx):
    if not holds(ctx, ctx.actor):
        return "nothing holds you"
    return True

def apply(ctx):
    me = ctx.actor
    done = []
    for pair in holds(ctx, me):
        k = pair[0]
        dc = int((pair[1].get("escape") or {}).get("dc") or 10)
        ath = bonus(me, "athletics", ctx)
        acr = bonus(me, "acrobatics", ctx)
        skill = "athletics" if ath >= acr else "acrobatics"
        m = max(ath, acr)  # bonus() carries exhaustion and thirst already
        roll = ctx.rand.roll("1d20")
        ok = roll + m >= dc
        ctx.emit("checked", target=me, reach=1, by=me.id, place=me.parent.id if me.parent else None, skill=skill,
                 roll=roll, mod=m, total=roll + m, dc=dc, success=ok, margin=roll + m - dc, why="escape " + k)
        if ok:
            drop_cond(ctx, me, k, "escaped")
            ctx.emit("escaped", target=me, reach=1, by=me.id, what=k)
        done.append({"from": k, "roll": roll, "total": roll + m, "dc": dc, "free": ok})
        ctx.log(skill + ": d20 " + str(roll) + " + " + str(m) + " = " + str(roll + m) + " vs " + str(dc)
                + (": free of the " + k if ok else ": still " + k))
    return {"tries": done}
