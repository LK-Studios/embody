def check(ctx):
    here = ctx.actor.parent
    if ctx.actor.state.dead:
        return "the dead lie still"
    if not ctx.actor.state.down:
        return "you are on your feet: walk"
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            # what stops a walk stops a crawl: a door shut or locked on the way, a place locked
            via = e["data"].get("via")
            if via and ctx.shut(ctx.get(via)):
                return ctx.shut(ctx.get(via))
            if via and not ctx.get(via).state.open:
                return "the way is shut"
            if ctx.shut(ctx.target):
                return ctx.shut(ctx.target)
            return True
    return "there is no way there from here"

def apply(ctx):
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=-1, who=ctx.actor.id, place=ctx.target.id, quiet=True, crawled=True)
