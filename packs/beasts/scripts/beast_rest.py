use("beasts")
def tick(ctx):
    # rest heals a beast: a point of hp a beat (the world's pace for beast_rest), with no water to pay, as people's
    # mend does. Not while it fights or hunts (attacked_by, stalking, prowling); a hungry beast mends at half the pace
    # (a point every second beat); asleep it mends two a beat. One a wound put down gets up at 2. The species' (or
    # the beast's) `rest_mends` sets the points a beat, 0 for none.
    b = ctx.self
    st = b.state
    if not able(b) or st.attacked_by or st.stalking or st.prowling:
        return
    v = int(st.hp or 0)
    mx = int(st.max_hp or 6)
    if v >= mx:
        return
    per = int(sv(b, species_of(ctx, b), "rest_mends", 1))
    if per <= 0:
        return
    changes = {}
    if st.hungry:
        owed = int(st.rest_owed or 0) + 1
        changes["rest_owed"] = owed % 2
        if owed < 2:
            ctx.patch(b, changes)
            return
    v = min(mx, v + (per * 2 if st.asleep else per))
    changes["hp"] = v
    if v > mx // 2 and st.wounded:
        changes["wounded"] = False
    rose = bool(st.down and st.downed_by != "thirst" and v >= 2)
    if rose:
        changes["down"] = False
    ctx.patch(b, changes)
    ctx.emit("mended", target=b, reach=0, hp=v, wounded=changes.get("wounded", st.wounded), by="rest")
    if rose:
        ctx.emit("rose", target=b, reach=1, by="rest")
