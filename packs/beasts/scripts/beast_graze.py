use("beasts")
# Graze: a beast with a seat eats a meal off its place's forage of its diet, the same forage the day draws on, so what
# it eats the herd here goes without. Ten minutes of cropping; at most once in `cooldown` (six world hours).

def check(ctx):
    b = ctx.actor
    if not b.state.species:
        return "only a beast grazes"
    if b.parent is None or b.state.dead:
        return b.name + " can't graze now"
    if b.state.down:
        return b.name + " is down"
    sp = species_of(ctx, b)
    eats = diet(b, sp)
    if forage_left(b.parent, eats) <= 0:
        return "nothing grows here that " + b.name + " eats" + (" (it eats " + ", ".join(eats) + ")" if eats else "")
    mx = int(sv(b, sp, "fed_max", 3))
    if int(b.state.fed or 0) >= mx:
        return b.name + " is not hungry"
    return True

def apply(ctx):
    b = ctx.actor
    sp = species_of(ctx, b)
    eats = diet(b, sp)
    got = eat_forage(ctx, b.parent, eats, 1)
    mx = int(sv(b, sp, "fed_max", 3))
    fed = min(mx, int(b.state.fed or 0) + got)
    ctx.patch(b, {"fed": fed, "hungry": False, "hungry_days": 0})
    ctx.emit("grazed", target=b.parent, reach=1, by=b.id, place=b.parent.id, left=forage_left(b.parent, eats), fed=fed)
