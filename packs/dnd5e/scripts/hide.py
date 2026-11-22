use("common")
use("five")
# Hide: stealth against 15 (armour that clanks rolls with disadvantage). Hidden, your next attack has advantage and
# attacks on you disadvantage, until you attack or cast.

def check(ctx):
    me = ctx.actor
    if me.state.down:
        return "you are down"
    if incapacitated(ctx, me):
        return "you cannot act"
    if "hidden" in conds(ctx, me):
        return "you are hidden already"
    return True

def apply(ctx):
    me = ctx.actor
    noisy = False
    for it in held_things(me):
        if (it.state.armor or {}).get("stealth_dis"):
            noisy = True
    r = d20(ctx, False, noisy)
    m = bonus(me, "stealth", ctx)
    total = r[0] + m
    ok = total >= 15
    ctx.emit("checked", target=me, reach=0, by=me.id, place=me.parent.id if me.parent else None, skill="stealth",
             roll=r[0], mod=m, total=total, dc=15, success=ok, margin=total - 15, why="hide")
    if ok:
        add_cond(ctx, me, "hidden", {"by": me.id})
    ctx.log("stealth: d20 " + str(r[0]) + (" (disadvantage: your armour)" if noisy else "") + " + " + str(m) + " = "
            + str(total) + " vs 15: " + ("hidden" if ok else "seen"))
    return {"hidden": ok, "total": total}
