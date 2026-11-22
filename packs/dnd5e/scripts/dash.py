use("common")
use("five")

def check(ctx):
    if ctx.actor.state.down:
        return "you are down"
    return True

def apply(ctx):
    ctx.emit("dashed", target=ctx.actor, reach=1, by=ctx.actor.id)
    ctx.log("you have another move this turn" if ctx.actor.state.fight else "you hurry")
    return {"dashed": True}
