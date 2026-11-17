# The jackals' earth (Nate 2026-11-17, "a jackal hunt quest they can only do at night"): by day the dune jackals lie
# up in their holes under the burned crawler in the Bone Field, out of reach of any blade; at dusk they come up. A
# jackal that comes home in daylight goes to earth when it gets there. One out hunting, hurt, down or kept by someone
# stays where it is, so a fight is never cut short.
SPECIES = "dune jackal"

def wild_ones(ctx):
    return [b for b in ctx.find(type="beast", state={"species": SPECIES}, limit=50)
            if not b.state.dead and not b.state.owner]

def go_to_earth(ctx, b):
    if b.state.hidden or b.state.down or not b.state.home or b.parent is None or b.parent.id != b.state.home:
        return False
    if b.state.attacked_by and ctx.t - float(b.state.attacked_at or 0) < 600:
        return False
    ctx.patch(b, {"hidden": True, "denned": True})
    return True

def on(ctx, event):
    k = event.kind
    st = ctx.find(type="story", limit=1)
    day = not (st and st[0].state.wild_night)
    if k == "dusk":
        up = None
        for b in wild_ones(ctx):
            if b.state.denned:
                ctx.patch(b, {"hidden": False, "denned": False})
                up = b.parent
        if up is not None:
            ctx.emit("scene", target=up, reach=1, text="At dusk the jackals come up out of the holes under the burned "
                     "crawler, one after another, and stand with their noses to the wind.")
        return
    if k == "dawn":
        down = None
        for b in wild_ones(ctx):
            if go_to_earth(ctx, b):
                down = b.parent
        if down is not None:
            ctx.emit("scene", target=down, reach=1, text="With the light the jackals slip one by one into the holes "
                     "under the burned crawler. By day they lie up deep, where no blade reaches.")
        return
    if not day:  # at dawn the flag may not be cleared yet: dawn is handled above
        return
    if k in ("arrived", "beast_went_home"):
        who = ctx.get(event.payload.get("by") if k == "beast_went_home" else event.payload.get("who"))
        if who is None or who.state.species != SPECIES or who.state.owner or who.state.dead:
            return
        if go_to_earth(ctx, who):
            ctx.emit("scene", target=who.parent, reach=1, text=who.name + " noses into the holes under the burned "
                     "crawler and is gone.")
        return
