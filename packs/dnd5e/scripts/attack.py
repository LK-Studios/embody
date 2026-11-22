use("common")
use("five")
# A blow with what you hold (or bare hands). The first one in a place rolls initiative; if someone is faster, the blow
# is declared and lands when your turn comes.

def check(ctx):
    me = ctx.actor
    t = ctx.target
    p = ctx.params or {}
    why = can_strike(ctx, me, t)
    if why:
        return why
    if p.get("with") and melee_weapon(me, p.get("with")) is None:
        return "you hold no " + str(p.get("with")) + " to strike with"
    return True

def apply(ctx):
    return open_with(ctx, "attack")
