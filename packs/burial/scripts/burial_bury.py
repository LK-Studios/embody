use("burial")
# Bury a dead body here, where the place or a thing in it is a burial ground. The digging takes the action's time;
# when it is out, if the digger and the body are both still here, the body goes into a new grave.

def check(ctx):
    me = ctx.actor
    b = ctx.target
    if b is None or b.id == me.id:
        return "bury whom? name a dead body here"
    if not b.state.dead:
        return b.name + " is not dead"
    if b.state.buried_in:
        return b.name + " is buried already"
    if me.parent is None or b.parent is None or b.parent.id != me.parent.id:
        return b.name + " is not here"
    if burial_ground(ctx, me.parent) is None:
        return ("this is no burial ground: the dead are buried where the place, or a thing in it, is one "
                "(burial_ground); carry them to one, or ask where the dead are laid here")
    why = seat_holds(ctx, b)
    if why:
        return why
    why = digging_wrong(ctx, me)
    if why:
        return why
    if ctx.params.get("words") is not None:
        why = words_wrong(ctx, ctx.params.get("words"), int(setting(ctx, "words_max", 200)), "what you say over it")
        if why:
            return why
    if ctx.params.get("marker") is not None:
        why = marker_wrong(ctx, me, ctx.params.get("marker"))
        if why:
            return why
    return True

def apply(ctx):
    me = ctx.actor
    b = ctx.target
    spend_water(ctx, me)
    ctx.patch(me, {"burying": {"body": b.id, "at": me.parent.id}})
    ctx.emit("scene", target=me.parent, reach=1, text=me.name + " starts digging a grave for " + b.name + ".")
    ctx.log("you dig; stay here until it is done, and " + b.name + " lies in the grave")

def finish(ctx):
    me = ctx.get(ctx.actor.id)
    b = ctx.get(ctx.target.id) if ctx.target else None
    job = me.state.burying if me is not None else None
    if me is not None:
        ctx.patch(me, {"burying": None})
    if me is None or b is None or job is None or job.get("body") != b.id:
        return
    if me.parent is None or me.parent.id != job.get("at"):
        ctx.log("you left the grave half dug")
        return
    if b.parent is None or b.parent.id != job.get("at") or not b.state.dead or b.state.buried_in:
        ctx.log(b.name + " is no longer here to bury")
        return
    place = me.parent
    words = str(ctx.params.get("words") or "").strip() or None
    g = ctx.spawn("grave", place, name="Grave of " + b.name,
                  state={"lies": b.name, "buried_by": me.name, "buried_at": ctx.t, "words": words, "remains": b.id})
    ctx.move(b, g)
    ctx.patch(b, {"hidden": True, "buried_in": g.id})
    look(ctx, g)
    ctx.emit("buried", target=g, reach=1, by=me.id, grave=g.id, place=place.id, body=b.id, words=words)
    mk = held_named(ctx, me, ctx.params.get("marker")) if ctx.params.get("marker") else None
    if mk is not None and not mk.is_a("creature") and mk.state.portable is not False:
        set_marker(ctx, g, mk, me)
    ctx.log(b.name + " lies in the grave")
