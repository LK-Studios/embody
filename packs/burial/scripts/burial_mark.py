use("burial")
# Set a thing you hold at a grave's head as its marker: it stays there, attached, no longer portable.

def check(ctx):
    g = ctx.target
    if g.state.marker and ctx.get(g.state.marker) is not None:
        return g.name + " is marked already, with " + ctx.get(g.state.marker).name
    ref = ctx.params.get("item")
    if not ref:
        return "mark it with what? params item: a thing you hold"
    return marker_wrong(ctx, ctx.actor, ref) or True

def apply(ctx):
    set_marker(ctx, ctx.target, held_named(ctx, ctx.actor, ctx.params.get("item")), ctx.actor)
    ctx.log("you set it at the head of " + ctx.target.name)
