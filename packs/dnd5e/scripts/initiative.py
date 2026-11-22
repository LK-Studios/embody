use("common")
use("five")
# Roll initiative when a fight starts: give what your own d20 shows (params roll), or leave it out and the world rolls for
# you. The order is set, and the first turn opens, once every played body's roll is in.

def check(ctx):
    me = ctx.actor
    f = my_fight(ctx, me)
    if f is None:
        return "no fight is starting here"
    if me.id not in (f.state.rolling or []):
        if f.state.rolling:
            return "your initiative is in (" + str(me.state.initiative) + "); waiting on " + ", ".join(waiting_on(ctx, f))
        return "initiative is rolled when a fight starts; yours is " + str(me.state.initiative)
    face = (ctx.params or {}).get("roll")
    if face is not None:
        n = str(face).strip()
        if not n.isdigit() or int(n) < 1 or int(n) > 20:
            return "a d20 shows 1 to 20: give what yours shows, or leave roll out and the world rolls"
    return True

def apply(ctx):
    me = ctx.actor
    f = my_fight(ctx, me)
    face = (ctx.params or {}).get("roll")
    face = int(str(face).strip()) if face is not None else None
    e = set_initiative(ctx, f, me, face)
    line = ("your die shows " if face is not None else "the world rolls ") + str(e["roll"]) + " " + signed(init_mod(ctx, me)) + ": initiative " + str(e["init"])
    f = ctx.get(f.id)
    if f.state.rolling:
        ctx.log(line + ". Waiting on " + ", ".join(waiting_on(ctx, f)))
        return {"initiative": e["init"], "roll": e["roll"], "waiting_on": waiting_on(ctx, f)}
    f = begin_fight(ctx, f, None)
    if f is None:
        ctx.log(line + ". Nobody is left to fight")
        return {"initiative": e["init"], "roll": e["roll"]}
    cur = ctx.get(f.state.turn_of) if f.state.turn_of else None
    ctx.log(line + ". Initiative: " + order_text(ctx, f) + (". Your turn" if cur is not None and cur.id == me.id else ""))
    return {"initiative": e["init"], "roll": e["roll"], "order": order_text(ctx, f)}
