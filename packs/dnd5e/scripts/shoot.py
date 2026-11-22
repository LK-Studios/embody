use("common")
use("five")
# A shot from what you hold that fires, at someone here or one way over that you can see. Here, the first one rolls
# initiative; one way over, it flies without one.

def check(ctx):
    me = ctx.actor
    t = ctx.target
    if t.id == me.id:
        return "you would not"
    if me.state.dead:
        return "the dead do not fight"
    if me.state.down:
        return "you are down"
    if incapacitated(ctx, me):
        return "you cannot act"
    w = ranged(me)
    if w is None:
        return "you hold nothing that shoots"
    why = can_fire(me, w)
    if why:
        return why
    if not in_sight(ctx, me, t):
        return "you cannot see them from here"
    if t.state.dead:
        return "they are dead"
    if t.state.down:
        return "they are down: kill them, or spare them"
    if me.state.yielded == t.id:
        return "you yielded to them"
    why = ring_blocks(ctx, me, t)
    if why:
        return why
    return True

def apply(ctx):
    return open_with(ctx, "shoot")
