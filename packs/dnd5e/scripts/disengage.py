use("common")
use("five")

def check(ctx):
    if ctx.actor.state.down:
        return "you are down"
    if not ctx.actor.state.fight:
        return "you are in no fight to back out of"
    return True

def apply(ctx):
    ctx.patch(ctx.actor, {"disengaged": True})
    ctx.emit("disengaged", target=ctx.actor, reach=1, by=ctx.actor.id)
    ctx.log("leaving this turn draws no opportunity attacks")
    return {"disengaged": True}
