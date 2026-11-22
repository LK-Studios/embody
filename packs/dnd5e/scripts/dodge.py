use("common")
use("five")
# Dodge (and brace, the same): attacks on you have disadvantage and your dex saves advantage until your next turn.

def check(ctx):
    if ctx.actor.state.down:
        return "you are down"
    if incapacitated(ctx, ctx.actor):
        return "you cannot act"
    return True

def apply(ctx):
    me = ctx.actor
    ctx.patch(me, {"dodging": True, "braced": False})
    ctx.emit("dodging", target=me, reach=1, by=me.id)
    if not me.state.fight:
        ctx.log("you keep your guard up until you do something else")
    return {"dodging": True}
