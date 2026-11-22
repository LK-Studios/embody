use("common")
use("five")
def tick(ctx):
    # a fighter without a mind, outside a fight (in one, the fight takes its turns): it turns on the other in a duel,
    # on whoever struck it last while that grudge holds, then on anyone its side has outlawed, and that rolls
    # initiative. With a bow it also covers the ways out: foes one way over get a shot, no fight needed.
    me = ctx.self
    st = me.state
    if st.down or st.dead or st.asleep or me.parent is None or incapacitated(ctx, me):
        return
    if my_fight(ctx, me) is not None:
        return
    foe = None
    for d in ctx.relations(me, "duel"):
        for pid in d["participants"]:
            o = ctx.get(pid)
            if pid != me.id and upright(o) and o.parent.id == me.parent.id:
                foe = o
    bow = ranged(me)
    if bow is not None and can_fire(me, bow) is not None:
        bow = None
    if foe is None:
        last = ctx.get(st.attacked_by) if st.attacked_by else None
        if st.attacked_by and not grudge_holds(ctx, me, last, bow):
            ctx.patch(me, {"attacked_by": None, "attacked_at": None})
            last = None
        if last is not None and upright(last) and last.parent.id == me.parent.id and not in_ring(ctx, last):
            foe = last
    f = faction_of(ctx, me)
    hostile = (f.state.hostile or {}) if f is not None else {}
    if foe is None and f is not None:
        for p in ctx.children(me.parent, "creature"):
            if p.id != me.id and hostile.get(p.id) and upright(p) and not in_ring(ctx, p) and outlaw_of(ctx, f, p):
                foe = p
                break
    if foe is not None:
        fight = start_fight(ctx, me.parent, me, foe)
        if fight.state.turn_of == me.id:
            npc_turn(ctx, fight, me)
            schedule_next(ctx, fight, "done")
        return
    if bow is None:
        return
    for e in ctx.edges(me.parent, "connects_to", "out"):
        place = ctx.get(e["target"])
        if place is None:
            continue
        for p in ctx.children(place, "creature"):
            near = p.id == st.attacked_by or (hostile.get(p.id) and outlaw_of(ctx, f, p))
            if near and upright(p) and not in_ring(ctx, p) and in_sight(ctx, me, p) and ctx.strike_wait(me, p) <= 0:
                ward = held(p, "ward")
                if ward and ward.state.on:
                    continue
                fire(ctx, me, p, bow)
                ctx.mark_strike(me, p, bow.state.cooldown_x or 1)
                return

def grudge_holds(ctx, me, foe, bow):
    if foe is None or foe.parent is None or foe.state.dead or foe.state.yielded == me.id:
        return False
    if foe.parent.id != me.parent.id and not (bow is not None and in_sight(ctx, me, foe)):
        return False
    if me.state.attacked_at is None:
        ctx.patch(me, {"attacked_at": ctx.t})
        return True
    return ctx.t - float(me.state.attacked_at) < grudge_for(ctx)
