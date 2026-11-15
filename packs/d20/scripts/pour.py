use("common")
def vessel(it):
    # something that holds a count of water: a skin (capacity), or a jar, cask or cistern (water_source with left)
    return it is not None and it.state.left is not None and (it.state.capacity is not None or bool(it.state.water_source))

def poured_from(ctx):
    # params.item names the vessel you hold (id or name); none: the first one you hold with water in it
    ref = (ctx.params or {}).get("item")
    for it in ctx.actor.children():
        if ref:
            if it.id == ref or it.name.lower() == str(ref).lower():
                return it
        elif vessel(it) and int(it.state.left) > 0 and it.id != ctx.target.id:
            return it
    return None

def poured_into(ctx, src):
    # a store or a skin you pour straight into, or, for a body, the first skin it holds with room
    t = ctx.target
    if not t.is_a("creature"):
        return t
    for it in t.children():
        if it.state.capacity is not None and it.state.left is not None and int(it.state.left) < int(it.state.capacity):
            if src is None or it.id != src.id:
                return it
    return None

def room(dst):
    # draws it still takes; None for a store with no capacity
    if dst.state.capacity is None:
        return None
    return max(0, int(dst.state.capacity) - int(dst.state.left))

def check(ctx):
    me, t = ctx.actor, ctx.target
    if t.id == me.id:
        return "pour it into something: a store here (a cask, a jar, a cistern), a skin, or someone here, into their skin"
    if t.parent is None or (t.parent.id != me.parent.id and t.parent.id != me.id):
        return t.name + " is not beside you: go where it stands, then pour"
    src = poured_from(ctx)
    ref = (ctx.params or {}).get("item")
    if src is None:
        if ref:
            return "you hold nothing called " + str(ref) + ": name a skin you hold, or leave item out"
        return "you hold nothing with water in it: fill a skin at a source first"
    if not vessel(src):
        return src.name + " holds no water: name a skin you hold, or leave item out"
    if int(src.state.left) <= 0:
        return src.name + " is empty: fill it at a source first"
    if t.is_a("creature"):
        if poured_into(ctx, src) is None:
            return t.name + " holds no skin with room in it: pour into a store here instead"
    elif endless(t):
        return t.name + " never runs dry: pouring into it adds nothing"
    elif not vessel(t):
        return t.name + " holds no water: pour into a store (a cask, a jar, a cistern), a skin, or someone here"
    dst = poured_into(ctx, src)
    if dst.id == src.id:
        return "that is the vessel you are pouring from: pour it into something else"
    if room(dst) == 0:
        return dst.name + " is full (" + str(int(dst.state.left)) + " of " + str(int(dst.state.capacity)) + ")"
    a = (ctx.params or {}).get("amount")
    if a is not None and not (str(a).isdigit() and int(str(a)) >= 1):
        return "amount is a number of draws, 1 or more (leave it out to pour it all)"
    return True

def apply(ctx):
    src = poured_from(ctx)
    dst = poured_into(ctx, src)
    have = int(src.state.left)
    a = (ctx.params or {}).get("amount")
    n = have if a is None else min(have, int(str(a)))
    space = room(dst)
    if space is not None:
        n = min(n, space)
    kept = have - n
    held = int(dst.state.left) + n
    ctx.patch(src, {"left": kept, "description": (src.state.description_empty or src.state.description) if kept <= 0 else src.state.description})
    ctx.patch(dst, {"left": held, "description": dst.state.description_full or dst.state.description})
    ctx.emit("poured", target=dst, reach=1, by=ctx.actor.id, item=src.id, store=dst.id, amount=n, left=held, kept=kept)
    of = (" of " + str(int(dst.state.capacity))) if dst.state.capacity is not None else ""
    ctx.log("poured " + str(n) + " into " + dst.name + " (" + str(held) + of + "); " + str(kept) + " left in " + src.name)
