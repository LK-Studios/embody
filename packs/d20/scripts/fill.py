use("common")
def source_here(ctx):
    return water_here(ctx, ctx.actor.parent)

def check(ctx):
    if ctx.target.parent.id != ctx.actor.id:
        # players tried fill on the well's cups: point at the skin they carry, or at drinking
        skin = held(ctx.actor, "capacity")
        if ctx.target.state.water_source or ctx.target.state.left is not None:
            if skin is None:
                return "fill takes a skin you carry, and you carry none: drink from " + ctx.target.name + " instead"
            return "fill takes the skin you carry: fill " + skin.name + " here, or drink from " + ctx.target.name
        return "you are not holding it: fill takes a skin in your hands"
    if ctx.target.state.capacity is None:
        return "it holds no water"
    if ctx.target.state.left is not None and int(ctx.target.state.left) >= int(ctx.target.state.capacity):
        return "it is already full: drink from it first"
    if source_here(ctx) is None:
        return "there is no water here to fill it from"
    return True

def apply(ctx):
    src = source_here(ctx)
    cap = int(ctx.target.state.capacity)
    if src.state.left is not None:
        ctx.patch(src, {"left": max(0, int(src.state.left) - 1)})
    ctx.patch(ctx.target, {"left": cap, "description": ctx.target.state.description_full or ctx.target.state.description})
    ctx.emit("filled", target=ctx.target, reach=1, by=ctx.actor.id, source=src.id)
