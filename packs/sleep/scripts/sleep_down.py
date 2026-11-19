def check(ctx):
    me = ctx.actor.state
    if me.dead:
        return "the dead do not sleep"
    if me.asleep:
        return "you are asleep already"
    return True

def apply(ctx):
    # lie down: you hear only what is loud or done to you, and a guard you held drops
    me = ctx.actor
    ctx.patch(me, {"asleep": True, **({"braced": False} if me.state.braced else {})})
    ctx.emit("slept", target=me, reach=1, by=me.id, place=me.parent.id if me.parent else None)
    ctx.log("you sleep; something loud, a hand on you or your next deed wakes you")
