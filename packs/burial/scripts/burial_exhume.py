use("burial")
# Dig a body up again. When the time is out, if the digger is still there, the body lies where the grave was, the
# marker lies loose beside it, and the grave is gone. The dead one's people hold it against the digger.

def check(ctx):
    g = ctx.target
    if g.state.remains is None or ctx.get(g.state.remains) is None:
        return "nobody lies in " + g.name
    return digging_wrong(ctx, ctx.actor) or True

def apply(ctx):
    me = ctx.actor
    g = ctx.target
    spend_water(ctx, me)
    ctx.patch(me, {"exhuming": {"grave": g.id, "at": me.parent.id}})
    ctx.emit("scene", target=g.parent, reach=1, text=me.name + " starts digging up " + g.name + ".")
    ctx.log("you dig; stay here until it is done")

def finish(ctx):
    me = ctx.get(ctx.actor.id)
    g = ctx.get(ctx.target.id) if ctx.target else None
    job = me.state.exhuming if me is not None else None
    if me is not None:
        ctx.patch(me, {"exhuming": None})
    if me is None or g is None or job is None or job.get("grave") != g.id:
        return
    if me.parent is None or g.parent is None or me.parent.id != job.get("at") or g.parent.id != job.get("at"):
        ctx.log("you left before you were down to them")
        return
    b = ctx.get(g.state.remains)
    if b is None:
        ctx.log("nobody lies there now")
        return
    place = g.parent
    ctx.move(b, place)
    ctx.patch(b, {"hidden": False, "buried_in": None})
    mk = ctx.get(g.state.marker) if g.state.marker else None
    if mk is not None:
        ctx.move(mk, place)
        ctx.patch(mk, {"portable": True, "attached": None, "marker_of": None})
    crime = bool(setting(ctx, "exhume_crime", False))
    ctx.emit("exhumed", target=g, reach=1, by=me.id, grave=g.id, place=place.id, body=b.id, crime=crime)
    cost = int(setting(ctx, "exhume_standing", -2))
    f = faction_of(ctx, b)
    if f is not None and cost != 0:
        shift_standing(ctx, me, f, cost, "exhumed " + b.name)
    ctx.destroy(g)
    ctx.log(b.name + " is out of the ground")
