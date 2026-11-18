def check(ctx):
    if ctx.actor.state.down:
        return "you are down: crawl"
    for e in ctx.edges(ctx.actor.parent, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            if ctx.target.state.hidden and ctx.target.state.known_to != ctx.actor.state.faction:
                return "you do not know the way"
            return True
    return "there is no way there from here"

def apply(ctx):
    # the quiet step: twice as long as go, and deep sand does not count it
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=-1, who=ctx.actor.id, place=ctx.target.id, quiet=True)
