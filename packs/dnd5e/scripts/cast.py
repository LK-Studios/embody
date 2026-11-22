use("common")
use("five")
# Cast a spell you know at someone here (or one way over, for a spell that reaches that far), or at yourself. A harmful
# spell is a hostile deed: the first one in a place rolls initiative.

def check(ctx):
    me = ctx.actor
    t = ctx.target if ctx.target is not None else me
    p = ctx.params or {}
    name = str(p.get("spell") or "").strip().lower()
    sc = me.state.spellcasting or {}
    if not sc:
        return "you cast no spells"
    if not name:
        return "name the spell: params {spell}; you know " + ", ".join(sc.get("spells") or [])
    if not knows(me, name):
        return "you do not know " + name + "; you know " + ", ".join(sc.get("spells") or [])
    sp = spell_of(ctx, me, name)
    if sp is None:
        return "this world has no spell called " + name
    if me.state.down or incapacitated(ctx, me):
        return "you cannot cast now"
    lv = int(p.get("level") or sp.get("level") or 0)
    if int(sp.get("level") or 0) > 0:
        if lv < int(sp.get("level")):
            return name + " needs a slot of level " + str(sp.get("level")) + " or higher"
        if int(((sc.get("slots") or {}).get(str(lv))) or 0) <= 0:
            return "you have no level " + str(lv) + " slot left (" + slots_text(sc) + "); a long rest brings them back"
    rng = sp.get("range") or "here"
    if rng == "self" or sp.get("target") == "self":
        if t.id != me.id:
            return name + " is cast on yourself"
    elif t.id != me.id or harmful_spell(sp):
        if t.id == me.id and harmful_spell(sp):
            return "not on yourself"
        if rng == "sight":
            if not in_sight(ctx, me, t):
                return "you cannot see them from here"
        elif t.parent is None or t.parent.id != me.parent.id:
            return "they are not here: " + name + " reaches only someone here"
    if t.state.dead:
        return "they are dead"
    if harmful_spell(sp):
        if t.state.down:
            return "they are down: kill them, or spare them"
        why = ring_blocks(ctx, me, t)
        if why:
            return why
    return True

def slots_text(sc):
    out = []
    for k in sorted((sc.get("slots") or {}).keys()):
        out.append("level " + k + ": " + str((sc.get("slots") or {}).get(k)))
    return ", ".join(out) or "none"

def apply(ctx):
    me = ctx.actor
    t = ctx.target if ctx.target is not None else me
    p = ctx.params or {}
    name = str(p.get("spell") or "").strip().lower()
    sp = spell_of(ctx, me, name)
    lv = int(p.get("level") or sp.get("level") or 0)
    if harmful_spell(sp) and t.parent is not None and t.parent.id == me.parent.id and my_fight(ctx, me) is None:
        f = start_fight(ctx, me.parent, me, t)
        if f.state.turn_of != me.id:
            ctx.log("initiative: " + order_text(ctx, f) + ". You act after " + ", ".join(ahead_of(f, me))
                    + ": cast it again on your turn")
            return {"waiting": True, "initiative": order_text(ctx, f)}
        pay(ctx, me, sp.get("time") or "action", "cast")
        r = cast_spell(ctx, me, t, name, sp, lv)
        r["initiative"] = order_text(ctx, f)
        if turn_done(ctx, me, "cast"):
            schedule_next(ctx, f, "done")
        return r
    return cast_spell(ctx, me, t, name, sp, lv)
