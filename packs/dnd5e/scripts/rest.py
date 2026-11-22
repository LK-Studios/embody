use("common")
use("five")
# A short rest: an hour of nothing much. At its end, spend hit dice (params dice): each heals its roll + con. A
# warlock's pact slots come back too.

def check(ctx):
    me = ctx.actor
    st = me.state
    if my_fight(ctx, me) is not None:
        return "not in a fight"
    if st.down:
        return "you are down: someone must see to you first"
    sc = st.spellcasting or {}
    if int(st.hp or 0) >= int(st.max_hp or 0) and not (sc.get("pact") and sc.get("slots") != sc.get("slots_max")):
        return "you are whole: nothing to rest off"
    if int(st.hit_dice or 0) <= 0 and not sc.get("pact"):
        return "you have no hit dice left: a long rest (a night's sleep) brings half of them back"
    return True

def apply(ctx):
    ctx.emit("resting", target=ctx.actor, reach=1, by=ctx.actor.id)
    ctx.log("you rest for an hour")
    return {"resting": True}

def finish(ctx):
    me = ctx.actor
    st = me.state
    p = ctx.params or {}
    want = p.get("dice")
    left = int(st.hit_dice or 0)
    die = st.hit_die or "1d8"
    hp = int(st.hp or 0)
    mx = int(st.max_hp or 0)
    spent = 0
    healed = 0
    while left > 0 and hp < mx and (want is None or spent < int(want)):
        n = max(1, ctx.rand.roll(die) + amod(me, "con"))
        hp = min(mx, hp + n)
        healed = healed + n
        left = left - 1
        spent = spent + 1
    changes = {"hp": hp, "hit_dice": left}
    sc = st.spellcasting or {}
    if sc.get("pact") and sc.get("slots_max"):
        changes["spellcasting"] = {"slots": dict(sc.get("slots_max"))}
    ctx.patch(me, changes)
    ctx.emit("rested", target=me, reach=0, rest="short", hp=hp, spent=spent, hit_dice=left)
    ctx.log("short rest: " + str(spent) + " hit dice, hp " + str(hp) + "/" + str(mx))
