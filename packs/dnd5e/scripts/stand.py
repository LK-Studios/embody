use("common")
use("five")

def check(ctx):
    me = ctx.actor
    if me.state.down:
        return "you are down: someone must heal or stabilise you"
    if "prone" not in conds(ctx, me):
        return "you are on your feet"
    return True

def apply(ctx):
    drop_cond(ctx, ctx.actor, "prone", "stood")
    ctx.log("you get up")
    return {"stood": True}
