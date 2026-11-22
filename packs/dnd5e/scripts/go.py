use("common")
use("five")
# The village pack's go, with a fight's price: leaving a place where a foe stands draws its opportunity attack (unless
# you disengaged), and a blow that drops you on the way out keeps you here.

def shut(ctx, x):
    return ctx.shut(x)

def check(ctx):
    here = ctx.actor.parent
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == ctx.target.id:
            via = e["data"].get("via")
            if via and shut(ctx, ctx.get(via)):
                return shut(ctx, ctx.get(via))
            if via and not ctx.get(via).state.open:
                return "the way is shut"
            if shut(ctx, ctx.target):
                return shut(ctx, ctx.target)
            return True
    return "there is no way there from here"

def apply(ctx):
    here = ctx.actor.parent
    swung = opportunity(ctx, ctx.actor)
    if ctx.actor.state.down or ctx.actor.state.dead:
        ctx.log("you go down before you reach the way out")
        return {"stopped": True, "opportunity": swung}
    ctx.move(ctx.actor, ctx.target)
    ctx.emit("arrived", target=ctx.target, reach=-1, who=ctx.actor.id, place=ctx.target.id)
    # whoever follows you comes along: the dog you fed, anyone told to follow, and whoever follows them in turn; a
    # sleeper stays, and so does a body down or dead (it is carried, not led), and anyone in a fight here
    led = [ctx.actor.id]
    for depth in range(32):
        came = []
        for p in ctx.children(here):
            lead = p.state.follows if p.state.follows in led else (p.state.friend if p.state.friend in led else None)
            if lead is not None and not (p.state.asleep or p.state.down or p.state.dead or p.state.fight):
                ctx.move(p, ctx.target)
                ctx.emit("arrived", target=ctx.target, reach=1, who=p.id, place=ctx.target.id, following=lead)
                came.append(p.id)
        if not came:
            break
        led = came
    return {"opportunity": swung} if swung else None
