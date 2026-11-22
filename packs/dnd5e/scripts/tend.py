use("common")
use("five")
# See to someone here (or yourself). Medicine in hand (a thing with doses and `heals`, dice like "2d4+2") heals what it
# heals, no roll, down or up. Bare hands: a medicine check (wis) against 10 stabilises the dying. Thirst's down is
# water's: d20's way, a draw of water washed in and survival against 12 gets them up at 1.

def medicine_in_hand(me):
    for it in me.children():
        if it.state.medicine and int(it.state.doses or 0) > 0:
            return it
    return None

def wash_water(ctx, me):
    for it in me.children():
        if it.state.capacity is not None and int(it.state.left or 0) > 0:
            return it
    return water_here(ctx, me.parent)

def check(ctx):
    me = ctx.actor
    t = ctx.target
    if t.parent is None or (t.parent.id != me.parent.id and t.id != me.id):
        return "they are not here"
    if t.state.dead:
        return "they are past tending"
    if me.state.down and t.id == me.id:
        return "you are down: someone else must tend you"
    med = medicine_in_hand(me)
    hurt = int(t.state.hp or 0) < int(t.state.max_hp or 0)
    if med is not None and (hurt or t.state.down):
        return True
    if t.state.down and t.state.downed_by == "thirst":
        if wash_water(ctx, me) is None:
            return "a wound bound dry festers: hold a skin with water in it, or tend them beside a cask or a source"
        return True
    if t.state.down and t.state.dying:
        return True
    if t.state.down:
        return "they are stable: they wake on their own in a few hours, or heal them now with medicine or a spell"
    if not hurt:
        return "they are whole: nothing to tend"
    return "bare hands do nothing for someone on their feet: bring medicine, or rest (a short rest spends hit dice)"

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    med = medicine_in_hand(me)
    if med is not None and (int(t.state.hp or 0) < int(t.state.max_hp or 0) or t.state.down):
        doses = int(med.state.doses or 0) - 1
        h = med.state.heals or 3
        n = roll_dice(ctx, h, False) if isinstance(h, str) else int(h)
        ctx.patch(med, {"doses": doses, "description": (med.state.description_empty or "Used up.") if doses <= 0 else med.state.description})
        got = heal(ctx, t, n, me, med.name)
        ctx.emit("tended", target=t, reach=1, by=me.id, medicine=med.name, success=True, hp=t.state.hp)
        ctx.log(med.name + ": " + str(got) + " hp, now " + str(t.state.hp))
        return {"hp": t.state.hp, "healed": got}
    if t.state.downed_by == "thirst":
        src = wash_water(ctx, me)
        if src.state.left is not None:
            ctx.patch(src, {"left": int(src.state.left) - 1})
        roll = ctx.rand.roll("1d20")
        ok = roll + bonus(me, "survival", ctx) >= 12
        if ok:
            heal(ctx, t, 1, me, "tended")
        ctx.emit("tended", target=t, reach=1, by=me.id, washed_with=src.id, roll=roll, success=ok, hp=t.state.hp)
        return {"success": ok}
    roll = ctx.rand.roll("1d20")
    m = bonus(me, "medicine", ctx) if known_skill(ctx, me, "medicine") else amod(me, "wis") + test_mod(ctx, me)
    ok = roll + m >= 10
    if ok:
        stabilize(ctx, t, me)
    ctx.emit("tended", target=t, reach=1, by=me.id, roll=roll, mod=m, total=roll + m, dc=10, success=ok, hp=t.state.hp)
    ctx.log("medicine: d20 " + str(roll) + " + " + str(m) + " = " + str(roll + m) + " vs 10: "
            + ("stable: they will wake in a few hours" if ok else "they are still slipping"))
    return {"success": ok, "stable": ok}
