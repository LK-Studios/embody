use("common")
use("five")

def check(ctx):
    why = can_strike(ctx, ctx.actor, ctx.target)
    if why:
        return why
    if "grappled" in conds(ctx, ctx.target) and conds(ctx, ctx.target)["grappled"].get("by") == ctx.actor.id:
        return "you have hold of them already"
    return True

def apply(ctx):
    return open_with(ctx, "grapple")
