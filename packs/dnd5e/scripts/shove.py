use("common")
use("five")

def check(ctx):
    why = can_strike(ctx, ctx.actor, ctx.target)
    if why:
        return why
    if "prone" in conds(ctx, ctx.target):
        return "they are on the floor already"
    return True

def apply(ctx):
    return open_with(ctx, "shove")
