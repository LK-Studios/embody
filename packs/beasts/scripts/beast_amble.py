use("beasts")
def tick(ctx):
    # a beast nobody holds moves about its place now and then (its `amble`): a few steps in some direction, back toward
    # its herd when it has strayed, inside the place and out of anything solid, facing the way it goes. Only where it
    # can be seen: someone holds a body here, or the place says `amble` (a game's client watches it); each step is two
    # events. One with no spot of its own takes a free one by its herd first, wherever it is, so beasts that walk in
    # spread out instead of standing on one point.
    b = ctx.self
    st = b.state
    if not able(b) or st.down or st.asleep or st.attacked_by:
        return
    place = b.parent
    if not (place.state.layout or {}).get("at"):
        return  # a place with no extent of its own: nowhere to amble
    am = sv(b, species_of(ctx, b), "amble", True)
    if not am:
        return
    am = am if isinstance(am, dict) else {}
    here = (st.layout or {}).get("at")
    if here and not place.state.amble and not seen(ctx, place):
        return
    if here and not ctx.rand.chance(float(am.get("chance", 0.5))):
        return
    herd = herd_spot(ctx, b, place)
    if not here:
        ctx.step(b, to=[herd[0], herd[1]], max_m=0)
        return
    lo, hi = (am.get("step_m") or [1, 4])[0], (am.get("step_m") or [1, 4])[-1]
    d = float(lo) + ctx.rand.random() * (float(hi) - float(lo))
    dx = herd[0] - here[0]
    dy = herd[1] - here[1]
    far = (dx * dx + dy * dy) ** 0.5
    if far > float(am.get("herd_m", 8)):
        ux = dx / far
        uy = dy / far
    else:
        ux = 0.0
        uy = 0.0
        for i in range(8):
            x = ctx.rand.random() * 2 - 1
            y = ctx.rand.random() * 2 - 1
            r = (x * x + y * y) ** 0.5
            if r > 0.1 and r <= 1:
                ux = x / r
                uy = y / r
                break
        if ux == 0.0 and uy == 0.0:
            return
    ctx.step(b, to=[here[0] + ux * d, here[1] + uy * d], max_m=d)

def seen(ctx, place):
    for c in ctx.children(place):
        if ctx.embodied(c):
            return True
    return False

def herd_spot(ctx, b, place):
    # where its herd stands: the middle of the others of its kind here that have spots, else the middle of the place
    xs = []
    ys = []
    for c in ctx.children(place, "beast"):
        at = (c.state.layout or {}).get("at")
        if c.id != b.id and at and c.state.species == b.state.species and not c.state.dead:
            xs.append(at[0])
            ys.append(at[1])
    if xs:
        return [sum(xs) / len(xs), sum(ys) / len(ys)]
    at = place.state.layout.get("at")
    return [at[0], at[1]]
