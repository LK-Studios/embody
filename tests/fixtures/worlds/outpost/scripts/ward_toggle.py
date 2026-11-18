def check(ctx):
    if ctx.self.parent.id != ctx.actor.id:
        return "you must hold it"
    return True

def apply(ctx):
    on = not ctx.self.state.on
    ctx.patch(ctx.self, {"on": on})
    ctx.emit("ward_" + ("on" if on else "off"), target=ctx.actor, reach=1)
