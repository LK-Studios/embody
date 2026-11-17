use("burial")
# Cut a line into a grave's marker, or its headboard when it has none. One inscription; only whoever cut it may cut it
# again, unless the world says otherwise (root burial.inscribe_over).

def check(ctx):
    g = ctx.target
    why = words_wrong(ctx, ctx.params.get("text"), int(setting(ctx, "inscription_max", 120)), "the inscription")
    if why:
        return why
    if g.state.inscription and g.state.inscribed_by != ctx.actor.id and not setting(ctx, "inscribe_over", False):
        return "something is cut into it already, and only whoever cut it may cut it again"
    return True

def apply(ctx):
    g = ctx.target
    text = str(ctx.params.get("text")).strip()
    ctx.patch(g, {"inscription": text, "inscribed_by": ctx.actor.id})
    mk = ctx.get(g.state.marker) if g.state.marker else None
    if mk is not None:
        ctx.patch(mk, {"text": text})
    look(ctx, g)
    ctx.emit("inscribed", target=g, reach=1, by=ctx.actor.id, grave=g.id, place=g.parent.id, text=text)
    ctx.log("you cut it into " + (mk.name if mk is not None else "the headboard"))
