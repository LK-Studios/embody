use("burial")
# A dead seat's leave: the living may bury its body now, without the world's wait.

def check(ctx):
    me = ctx.actor
    if ctx.self is not None and ctx.self.id != me.id:
        return "only the dead one's own seat gives that leave"
    if not me.state.dead:
        return "you are not dead"
    if me.state.burial_leave:
        return "you have given your leave already"
    return True

def apply(ctx):
    me = ctx.actor
    ctx.patch(me, {"burial_leave": True})
    ctx.emit("left_to_bury", target=me, reach=1, body=me.id)
    ctx.log("the living may bury you now")
