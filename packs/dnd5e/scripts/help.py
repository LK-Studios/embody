use("common")
use("five")
# Help an ally here: their next attack on someone at odds with you has advantage.

def check(ctx):
    me = ctx.actor
    t = ctx.target
    if t.id == me.id:
        return "help someone else"
    if t.parent is None or t.parent.id != me.parent.id:
        return "they are not here"
    if me.state.down:
        return "you are down"
    if t.state.dead:
        return "they are past help"
    return True

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    entry = {"by": me.id, "once": True}
    if t.state.fight:
        entry["rounds"] = 1
    else:
        entry["until"] = ctx.t + 6
    add_cond(ctx, t, "helped", entry)
    ctx.emit("helped", target=t, reach=1, by=me.id)
    ctx.log(t.name + "'s next attack on a foe of yours has advantage")
    return {"helped": t.id}
