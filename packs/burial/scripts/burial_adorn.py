use("burial")
# Leave something on a grave: a short line added to how it looks, dated in its state. The oldest stay; a full grave
# takes no more (root burial.adorn_max).

def check(ctx):
    g = ctx.target
    why = words_wrong(ctx, ctx.params.get("text"), int(setting(ctx, "adorn_line_max", 80)), "what you leave")
    if why:
        return why
    most = int(setting(ctx, "adorn_max", 8))
    if len(g.state.adornments or []) >= most:
        return g.name + " has all it can hold already (" + str(most) + " things left on it)"
    return True

def apply(ctx):
    g = ctx.target
    text = str(ctx.params.get("text")).strip()
    rows = list(g.state.adornments or [])
    rows.append({"text": text, "by": ctx.actor.name, "t": ctx.t})
    ctx.patch(g, {"adornments": rows})
    look(ctx, g)
    ctx.emit("adorned", target=g, reach=1, by=ctx.actor.id, grave=g.id, place=g.parent.id, text=text)
    ctx.log("you leave it on " + g.name)
