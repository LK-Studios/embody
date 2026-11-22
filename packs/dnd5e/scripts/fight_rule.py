use("common")
use("five")
# On the root: whose turn it is, what a deed costs, who joins and leaves a fight, the next turns, and a night's rest.

def on(ctx, event):
    k = event.kind
    if k == "before_act":
        gate(ctx, event)
    elif k == "act":
        spend(ctx, event)
    elif k == "fight_next":
        next_turn(ctx, event)
    elif k == "arrived":
        arrived(ctx, event)
    elif k == "slept":
        who = ctx.get(event.target)
        if who is not None and who.is_a("creature"):
            ctx.patch(who, {"slept_at": ctx.t})
    elif k == "woke":
        woke(ctx, event)
    elif k == "died" or k == "killed":
        gone(ctx, event)
    elif k == "come_round":
        who = ctx.get(event.target)
        if who is not None:
            come_round(ctx, who)

def harmful_deed(ctx, who, verb, params):
    if verb in HARMFUL:
        return True
    if verb == "cast":
        return harmful_spell(spell_of(ctx, who, (params or {}).get("spell")))
    return False

def gate(ctx, event):
    # refuses what the moment does not allow, and writes nothing: perceive asks this too
    a = ctx.get(event.actor) if event.actor else None
    if a is None or not a.is_a("creature"):
        return
    verb = event.payload.get("verb")
    params = event.payload.get("params") or {}
    t = ctx.get(event.target) if event.target and event.target != a.id else None
    cost = cost_of(ctx, a, verb, t, params)
    c = conds(ctx, a)
    if cost == "move" and verb != "stand":
        for k in ["grappled", "restrained"]:
            if k in c:
                ctx.reject("you are " + k + ": you cannot move", "escape first (an action: athletics or acrobatics)")
    if t is not None and "charmed" in c and c["charmed"].get("by") == t.id and harmful_deed(ctx, a, verb, params):
        ctx.reject("you are charmed by " + t.name + ": you will not harm them", "the charm ends in time, or if they harm you")
    f = my_fight(ctx, a)
    if f is None or cost == "free" or cost == "reaction":
        return
    if f.state.turn_of != a.id:
        cur = ctx.get(f.state.turn_of) if f.state.turn_of else None
        ctx.reject("not your turn: " + (cur.name if cur is not None else "someone else") + " acts now (round "
                   + str(f.state.round) + ")",
                   "talk, yield or say something any time; your turn comes in initiative order: " + order_text(ctx, f))
    if cost == "object":
        return
    why = pay_check(ctx, a, cost, verb)
    if why:
        left = turn_left(ctx, a)
        ctx.reject(why, "end your turn (end)" + ("; still yours: " + ", ".join(left) if left else ""))

def spend(ctx, event):
    # the deed is on its way (this runs before it applies): pay for it, and end the turn when nothing is left
    a = ctx.get(event.actor) if event.actor else None
    if a is None or not a.is_a("creature"):
        return
    f = my_fight(ctx, a)
    if f is None or f.state.turn_of != a.id:
        return
    verb = event.payload.get("verb")
    params = event.payload.get("params") or {}
    t = ctx.get(event.payload.get("target")) if event.payload.get("target") else None
    if verb == "end":
        schedule_next(ctx, f, "done")
        return
    cost = cost_of(ctx, a, verb, t, params)
    if verb == "yield":
        schedule_next(ctx, f, "check")  # a yield may leave nobody at odds: the fight ends then, not at the round's end
    if cost == "free" or cost == "object" or cost == "reaction":
        return
    pay(ctx, a, cost, verb)
    if t is not None and t.id != a.id and harmful_deed(ctx, a, verb, params):
        mark_foes(ctx, a, t)
    if turn_done(ctx, a, verb):
        schedule_next(ctx, f, "done")

def next_turn(ctx, event):
    p = event.payload
    f = ctx.get(p.get("fight"))
    if f is None:
        return
    if int(p.get("round") or 0) != int(f.state.round or 0) or int(p.get("turn") or 0) != int(f.state.turn or 0):
        return  # that turn is already over
    why = p.get("why")
    cur = ctx.get(f.state.turn_of) if f.state.turn_of else None
    if why == "check":
        if not fight_live(ctx, f):
            end_fight(ctx, f, "calm")
        return
    if why == "wait":
        if cur is None or not is_held(ctx, cur):
            return
        q = ctx.quiet(cur)
        wait = held_wait(ctx)
        if q is not None and q < wait:
            ctx.schedule(wait - q, "fight_next", target=f.parent, payload=p)  # they are still at it: give them the rest
            return
        ctx.patch(cur, {"dodging": True})
        ctx.emit("turn_passed", target=f.parent, reach=1, who=cur.id, why="no deed in time: they dodge")
    elif why == "npc":
        if cur is not None and not is_held(ctx, cur):
            npc_turn(ctx, f, cur)
    advance(ctx, f, 40)

def arrived(ctx, event):
    who = ctx.get(event.payload.get("who"))
    place = ctx.get(event.payload.get("place"))
    if who is None or place is None or not who.is_a("creature"):
        return
    old = ctx.get(who.state.fight) if who.state.fight else None
    if old is not None and old.parent is not None and old.parent.id != place.id:
        leave_fight(ctx, old, who, "left")
        ctx.emit("left_fight", target=old.parent, reach=1, who=who.id)
    elif old is None and who.state.fight:
        ctx.patch(who, {"fight": None, "initiative": None, "turn": None})
    f = fight_in(ctx, place)
    if f is not None and who.state.fight != f.id:
        join_fight(ctx, f, who)

def gone(ctx, event):
    who = ctx.get(event.target)
    if who is None:
        return
    f = ctx.get(who.state.fight) if who.state.fight else None
    if f is not None and f.state.turn_of == who.id:
        schedule_next(ctx, f, "done")

def woke(ctx, event):
    # eight hours asleep, once a day, is a long rest: every hp, half the hit dice, every slot, a level of exhaustion
    who = ctx.get(event.target)
    if who is None or who.state.dead or who.state.down or not who.is_a("creature"):
        return
    since = who.state.slept_at
    ctx.patch(who, {"slept_at": None})
    if since is None or ctx.t - float(since) < 8 * 3600:
        return
    last = who.state.long_rest_at
    if last is not None and ctx.t - float(last) < 16 * 3600:
        return
    st = who.state
    sc = st.spellcasting or {}
    changes = {"hp": int(st.max_hp or st.hp or 1), "long_rest_at": ctx.t, "death_saves": None, "relentless_used": None,
               "exhaustion": max(0, int(st.exhaustion or 0) - 1)}
    if st.hit_dice_max is not None:
        changes["hit_dice"] = min(int(st.hit_dice_max), int(st.hit_dice or 0) + max(1, int(st.hit_dice_max) // 2))
    if sc.get("slots_max"):
        changes["spellcasting"] = {"slots": dict(sc.get("slots_max"))}
    ctx.patch(who, changes)
    ctx.emit("rested", target=who, reach=0, rest="long", hp=changes["hp"], hit_dice=changes.get("hit_dice"))
