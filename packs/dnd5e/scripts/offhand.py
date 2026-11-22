use("common")
use("five")
# Two weapons: after a blow with a light weapon, a bonus blow with the light one in your other hand, no modifier to
# its damage (unless the modifier is a minus).

def second(me):
    ws = [it for it in held_things(me) if it.state.weapon and not it.state.ranged]
    if len(ws) < 2 or "light" not in props(ws[0]) or "light" not in props(ws[1]):
        return None
    return ws[1]

def check(ctx):
    me = ctx.actor
    why = can_strike(ctx, me, ctx.target)
    if why:
        return why
    if second(me) is None:
        return "you need a light weapon in each hand"
    f = my_fight(ctx, me)
    if f is None or int((me.state.turn or {}).get("action") or 0) > 0:
        return "attack with your main hand first, then this"
    return True

def apply(ctx):
    return strike5(ctx, ctx.actor, ctx.target, second(ctx.actor), {"offhand": True})
