# The dnd5e pack's helpers. Every 5e script starts with use("common") (d20's) and then use("five"): a function defined
# here after d20's of the same name replaces it for that script. pack.py has the rules in words.

ABIL = {"str": "force", "dex": "poise", "con": "endurance", "int": "cognition", "wis": "acuity", "cha": "projection"}
FROM_STAT = {"str": "body", "dex": "body", "con": "body", "int": "wits", "wis": "wits", "cha": "will"}
DEFAULT_COSTS = {"talk": "free", "yield": "free", "end": "free", "stats": "free", "initiative": "free", "read": "free", "show": "free",
                 "watch": "free", "follow": "free", "stay": "free", "take": "object", "drop": "object", "give": "object",
                 "put": "object", "buy": "object", "draw": "object", "attack": "attack", "shoot": "attack", "grapple": "attack",
                 "shove": "attack", "offhand": "bonus", "go": "move", "stand": "move", "crawl": "move"}
HARMFUL = ["attack", "shoot", "grapple", "shove", "offhand", "kill", "threaten"]
INCAP = ["incapacitated", "paralyzed", "stunned", "unconscious", "petrified"]
NO_STR_DEX = ["paralyzed", "stunned", "unconscious", "petrified"]
CUNNING = ["dash", "disengage", "hide"]

# ---- the numbers of a body -----------------------------------------------------------------------------------------

def settings(ctx):
    return ctx.root().state.dnd5e or {}

def score(who, ab):
    st = who.state
    sc = (st.scores or {}).get(ab)
    if sc is None and st.sheet:
        sc = ((st.sheet or {}).get("attributes") or {}).get(ABIL.get(ab, ab))
    if sc is None:
        sc = 10 + 2 * int(st.get(FROM_STAT.get(ab, "wits")) or 0)
    return max(1, min(30, int(sc)))

def amod(who, ab):
    return (score(who, ab) - 10) // 2

def prof(who):
    st = who.state
    if st.prof is not None:
        return int(st.prof)
    lv = st.level if st.level is not None else st.cr
    if lv is None:
        return 2
    return 2 + (max(1, int(float(lv))) - 1) // 4

def test_mod(ctx, who):
    # what every d20 test of this body carries: exhaustion -2 a level, thirst -2
    st = who.state
    m = -2 * int(st.exhaustion or 0)
    if st.thirsty:
        m = m - 2
    return m

def held_things(who):
    return [it for it in who.children()]

def is_held(ctx, who):
    return ctx.embodied(who)

def name_of(ctx, x):
    v = ctx.get(x) if isinstance(x, str) else x
    return v.name if v is not None else str(x)

# ---- conditions ------------------------------------------------------------------------------------------------------

def conds(ctx, who):
    # the conditions on a body now ({name: entry}); one whose `until` has passed is gone. Down from wounds is
    # unconscious and prone; asleep is unconscious; down from thirst is prone.
    out = {}
    for k, v in (who.state.conditions or {}).items():
        if v is None:
            continue
        e = v if isinstance(v, dict) else {}
        u = e.get("until")
        if u is not None and float(u) <= ctx.t:
            continue
        out[k] = e
        for extra in e.get("also") or []:
            out[extra] = out.get(extra) or {"by": e.get("by"), "from": k}
    st = who.state
    if st.down and not st.dead:
        out["prone"] = out.get("prone") or {}
        if st.downed_by != "thirst":
            out["unconscious"] = out.get("unconscious") or {}
    if st.asleep and not st.dead:
        out["unconscious"] = out.get("unconscious") or {"asleep": True}
    return out

def incapacitated(ctx, who):
    c = conds(ctx, who)
    for k in INCAP:
        if k in c:
            return True
    return False

def add_cond(ctx, who, name, entry):
    e = dict(entry or {})
    if e.get("until_h") is not None:
        e["until"] = ctx.t + float(e.get("until_h")) * 3600
        e["until_h"] = None
    immune = who.state.immune_conditions or []
    if name in immune:
        return False
    if (who.state.conditions or {}).get(name) is not None:
        ctx.patch(who, {"conditions": {name: None}})  # a fresh one: nothing of the old entry stays
    ctx.patch(who, {"conditions": {name: e}})
    ctx.emit("condition", target=who, reach=1, name=name, on=True, by=e.get("by"))
    return True

def drop_cond(ctx, who, name, why):
    if (who.state.conditions or {}).get(name) is None:
        return False
    ctx.patch(who, {"conditions": {name: None}})
    ctx.emit("condition", target=who, reach=1, name=name, on=False, why=why)
    return True

def use_once(ctx, who, names):
    # a mark that lasts one use (help, guiding bolt, vicious mockery): spent when it counts
    for n in names:
        e = (who.state.conditions or {}).get(n)
        if e is not None and e.get("once"):
            ctx.patch(who, {"conditions": {n: None}})

# ---- armour class, weapons, attacks ----------------------------------------------------------------------------------

def armor_class(ctx, who):
    st = who.state
    c = conds(ctx, who)
    extra = int(st.ac_bonus or 0)
    for k, e in c.items():
        extra = extra + int(e.get("ac") or 0)
    if st.ac is not None:
        return int(st.ac) + extra
    dex = amod(who, "dex")
    best = None
    shield = 0
    for it in held_things(who):
        a = it.state.armor
        if not isinstance(a, dict):
            continue
        if a.get("shield"):
            shield = max(shield, int(a.get("ac") or 2) + int(it.state.bonus or 0))
            continue
        cap = a.get("dex_cap")
        v = int(a.get("ac") or 10) + int(it.state.bonus or 0) + (dex if cap is None else min(dex, int(cap)))
        if best is None or v > best:
            best = v
    if best is None:
        base = 10
        for k, e in c.items():
            if e.get("ac_base") is not None:
                base = max(base, int(e.get("ac_base")))
        best = (int(st.natural_ac) if st.natural_ac is not None else base) + dex
        u = st.unarmored
        if u and not (u == "wis" and shield):
            best = best + amod(who, u)
    return best + shield + extra

def melee_weapon(who, name=None):
    for it in held_things(who):
        if not it.state.weapon:
            continue
        if name and str(it.name).lower() != str(name).lower() and str(it.state.kind or "").lower() != str(name).lower():
            continue
        if it.state.ranged and "thrown" not in (it.state.properties or []):
            continue
        return it
    return None

def props(w):
    return list(w.state.properties or []) if w is not None else []

def weapon_ability(who, w, ranged):
    if w is None:
        if who.state.martial_arts and amod(who, "dex") > amod(who, "str"):
            return "dex"
        return "str"
    p = props(w)
    if "finesse" in p or (who.state.martial_arts and w.state.category == "simple"):
        return "dex" if amod(who, "dex") > amod(who, "str") else "str"
    if ranged and "thrown" not in p:
        return "dex"
    return "str"

def proficient(who, w):
    if w is None:
        return True
    wp = who.state.weapon_prof
    if wp is None:
        return True
    return ("all" in wp) or (w.state.category in wp) or (w.state.kind in wp) or (str(w.name).lower() in wp)

def attack_bonus(ctx, who, w, ranged):
    ab = weapon_ability(who, w, ranged)
    b = amod(who, ab) + (prof(who) if proficient(who, w) else 0) + test_mod(ctx, who)
    if w is not None:
        b = b + int(w.state.bonus or 0)
    return b

def damage_dice(who, w):
    # the dice a blow rolls: the weapon's, its versatile die when nothing else is held to grip with, bare hands 1
    if w is None:
        if who.state.martial_arts:
            return who.state.martial_arts
        return None
    if w.state.dice:
        if w.state.versatile and len([x for x in held_things(who) if x.state.weapon or (x.state.armor or {}).get("shield")]) == 1:
            return w.state.versatile
        return w.state.dice
    return None

def flat_damage(w):
    # a weapon from before dice (d20's fixed `damage`), or bare hands
    if w is None:
        return 1
    return int(w.state.damage or 1)

def roll_dice(ctx, dice, crit):
    # dice like "2d6+1": on a crit the dice roll twice, the number after the + once
    s = str(dice).replace(" ", "").lower()
    plus = 0
    if "+" in s:
        parts = s.split("+")
        s = parts[0]
        plus = int(parts[1])
    elif "-" in s[1:]:
        i = s.rfind("-")
        plus = -int(s[i + 1:])
        s = s[:i]
    total = ctx.rand.roll(s)
    if crit:
        total = total + ctx.rand.roll(s)
    return total + plus

def scale_cantrip(dice, level):
    # a cantrip's dice grow at levels 5, 11 and 17
    lv = int(level or 1)
    n = 1 + (1 if lv >= 5 else 0) + (1 if lv >= 11 else 0) + (1 if lv >= 17 else 0)
    if n == 1:
        return dice
    s = str(dice)
    d = s.split("d")
    return str(int(d[0] or 1) * n) + "d" + d[1]

def d20(ctx, adv, dis):
    a = ctx.rand.roll("1d20")
    if adv and not dis:
        b = ctx.rand.roll("1d20")
        return [max(a, b), [a, b], "advantage"]
    if dis and not adv:
        b = ctx.rand.roll("1d20")
        return [min(a, b), [a, b], "disadvantage"]
    return [a, [a], None]

def die_bonus(ctx, who):
    # bless and bane: +1d4 or -1d4 on attacks and saves
    c = conds(ctx, who)
    b = 0
    if "blessed" in c:
        b = b + ctx.rand.roll(c["blessed"].get("die") or "1d4")
    if "baned" in c:
        b = b - ctx.rand.roll(c["baned"].get("die") or "1d4")
    return b

def at_odds(ctx, a, b):
    # a and b are foes in the fight they share, or one has outlawed the other's side, and neither yielded to the other
    if a.id == b.id or a.state.yielded == b.id or b.state.yielded == a.id:
        return False
    f = ctx.get(a.state.fight) if a.state.fight else None
    if f is not None and b.id in ((f.state.foes or {}).get(a.id) or []):
        return True
    fa = faction_of(ctx, a)
    if fa is not None and (fa.state.hostile or {}).get(b.id) and outlaw_of(ctx, fa, b):
        return True
    fb = faction_of(ctx, b)
    if fb is not None and (fb.state.hostile or {}).get(a.id) and outlaw_of(ctx, fb, a):
        return True
    return False

def upright(p):
    return p is not None and p.parent is not None and not p.state.down and not p.state.dead

def engaged(ctx, me):
    # someone at odds with me stands here, able to fight: a shot from here is at disadvantage
    if me.parent is None:
        return False
    for p in ctx.children(me.parent, "creature"):
        if p.id != me.id and upright(p) and not incapacitated(ctx, p) and at_odds(ctx, me, p):
            return True
    return False

def attack_mode(ctx, me, t, ranged):
    # advantage and disadvantage from both sides' conditions; they never stack and cancel to a straight roll
    a = conds(ctx, me)
    d = conds(ctx, t)
    adv = []
    dis = []
    for k in ["invisible", "hidden"]:
        if k in a:
            adv.append("you are unseen")
        if k in d:
            dis.append("they are unseen")
    for k in ["blinded", "poisoned", "restrained", "prone"]:
        if k in a:
            dis.append("you are " + k)
    if "frightened" in a:
        src = ctx.get(a["frightened"].get("by")) if a["frightened"].get("by") else None
        if src is None or (src.parent is not None and me.parent is not None and src.parent.id == me.parent.id):
            dis.append("you are frightened")
    if "grappled" in a and a["grappled"].get("by") and a["grappled"].get("by") != t.id:
        dis.append("you are grappled by someone else")
    if "mocked" in a:
        dis.append("you were mocked")
    for k in ["blinded", "paralyzed", "restrained", "stunned", "unconscious", "petrified", "outlined", "guided"]:
        if k in d:
            adv.append("they are " + k)
    if "prone" in d:
        if ranged:
            dis.append("they are prone")
        else:
            adv.append("they are prone")
    if t.state.dodging and not incapacitated(ctx, t):
        dis.append("they are dodging")
    h = a.get("helped")
    if h is not None and (h.get("against") is None or h.get("against") == t.id or at_odds(ctx, ctx.get(h.get("by")) or me, t)):
        adv.append("you were helped")
    if ranged and engaged(ctx, me):
        dis.append("a foe is close")
    return [adv, dis]

def can_react(ctx, who):
    st = who.state
    if incapacitated(ctx, who) or "no_reactions" in conds(ctx, who):
        return False
    if st.fight:
        return int((st.turn or {}).get("reaction", 1) or 0) > 0
    return True

def spend_reaction(ctx, who):
    if who.state.fight:
        econ = dict(who.state.turn or {"action": 0, "bonus": 0, "move": 0, "reaction": 1})
        econ["reaction"] = 0
        ctx.patch(who, {"turn": econ})

def try_shield(ctx, t, total, ac):
    # a body that knows shield turns a hit into a miss with its reaction and a 1st-level slot, when +5 is enough
    sc = t.state.spellcasting or {}
    if "shield" not in (sc.get("spells") or []) or total >= ac + 5 or not can_react(ctx, t):
        return False
    lvl = lowest_slot(t, 1)
    if lvl is None:
        return False
    spend_slot(ctx, t, lvl)
    spend_reaction(ctx, t)
    add_cond(ctx, t, "shielded", {"ac": 5, "rounds": 1, "ends": "start", "by": t.id})
    ctx.emit("cast", target=t, reach=1, by=t.id, spell="shield", level=lvl, at=t.id, reaction=True)
    return True

def sneak_dice(ctx, me, t, w, ranged, adv, dis):
    # once a turn, a rogue's finesse or ranged hit with advantage, or with an ally of theirs standing by the target
    sa = me.state.sneak_attack
    if not sa or me.state.sneak_used or (w is not None and not ("finesse" in props(w) or ranged)) or w is None:
        return None
    if dis and not adv:
        return None
    if adv:
        return sa
    for p in ctx.children(t.parent, "creature"):
        if p.id != me.id and p.id != t.id and upright(p) and not incapacitated(ctx, p) and at_odds(ctx, p, t) and not at_odds(ctx, p, me):
            return sa
    return None

def strike5(ctx, me, t, w, opts):
    # one attack roll with a weapon (or bare hands): opts {ranged, offhand, knockout, opportunity, label, extra_dice}
    ranged = bool(opts.get("ranged"))
    provoke(ctx, me, t)
    mark_foes(ctx, me, t)
    ward = held(t, "ward")
    label = opts.get("label") or (w.name if w is not None else "bare hands")
    if ward and ward.state.on and not opts.get("slow"):
        ctx.emit("warded", target=t, reach=1, by=me.id, weapon=label, ranged=ranged)
        return {"hit": False, "warded": True}
    mode = attack_mode(ctx, me, t, ranged)
    adv = mode[0]
    dis = mode[1]
    r = d20(ctx, len(adv) > 0, len(dis) > 0)
    nat = r[0]
    bonus5 = attack_bonus(ctx, me, w, ranged) + die_bonus(ctx, me)
    total = nat + bonus5
    ac = armor_class(ctx, t) + (cover(t.parent) if ranged else 0)
    d = conds(ctx, t)
    crit = nat >= int(me.state.crit_range or 20)
    if not ranged and ("unconscious" in d or "paralyzed" in d):
        crit = True
    hit = nat != 1 and (nat >= int(me.state.crit_range or 20) or total >= ac)
    use_once(ctx, me, ["helped", "mocked"])
    if "hidden" in conds(ctx, me):
        drop_cond(ctx, me, "hidden", "attacked")
    shielded = False
    if hit and not crit and try_shield(ctx, t, total, ac):
        hit = False
        shielded = True
        ac = ac + 5
    if not hit:
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon=label, attack=total, ac=ac, rolls=r[1], mode=r[2],
                 natural=nat, ranged=ranged, shielded=shielded, opportunity=bool(opts.get("opportunity")))
        ctx.log(label + ": d20 " + str(nat) + (" (" + r[2] + ")" if r[2] else "") + " + " + str(bonus5) + " = " + str(total)
                + " vs AC " + str(ac) + ": miss" + (" (shield)" if shielded else ""))
        return {"hit": False, "attack": total, "ac": ac, "natural": nat}
    use_once(ctx, t, ["guided"])
    dice = opts.get("dice") or damage_dice(me, w)
    ab = weapon_ability(me, w, ranged)
    m = amod(me, ab)
    if opts.get("offhand") and m > 0:
        m = 0
    if dice:
        dmg = roll_dice(ctx, dice, crit) + m + (int(w.state.bonus or 0) if w is not None else 0)
    else:
        dmg = flat_damage(w) + m
    sa = sneak_dice(ctx, me, t, w, ranged, len(adv) > 0, len(dis) > 0)
    if sa:
        dmg = dmg + roll_dice(ctx, sa, crit)
        if me.state.fight:
            ctx.patch(me, {"sneak_used": True})
    if opts.get("extra_dice"):
        dmg = dmg + roll_dice(ctx, opts.get("extra_dice"), crit)
    dmg = max(0, dmg)
    dtype = (w.state.dtype if w is not None else None) or opts.get("dtype") or "bludgeoning"
    res = harm(ctx, t, dmg, dtype, me, crit, opts.get("knockout") or in_duel_with(ctx, me, t), label)
    ctx.emit("hit", target=t, reach=1, by=me.id, dmg=res["dmg"], rolled=dmg, dtype=dtype, weapon=label, attack=total, ac=ac,
             rolls=r[1], mode=r[2], natural=nat, crit=crit, hp=t.state.hp, ranged=ranged, sneak=bool(sa),
             opportunity=bool(opts.get("opportunity")))
    scar(ctx, t, res["dmg"], label)
    ctx.log(label + ": d20 " + str(nat) + (" (" + r[2] + ")" if r[2] else "") + " + " + str(bonus5) + " = " + str(total)
            + " vs AC " + str(ac) + ": " + ("CRIT, " if crit else "hit, ") + str(res["dmg"]) + " " + dtype
            + (" (sneak attack)" if sa else "") + (" " + res["note"] if res.get("note") else ""))
    return {"hit": True, "dmg": res["dmg"], "attack": total, "ac": ac, "natural": nat, "crit": crit}

def in_duel_with(ctx, a, b):
    for d in ctx.relations(a, "duel"):
        if b.id in d["participants"]:
            return True
    return False

# ---- damage, dying, healing ------------------------------------------------------------------------------------------

def adjust(ctx, t, dmg, dtype):
    st = t.state
    c = conds(ctx, t)
    imm = st.immune or []
    if dtype in imm or "all" in imm:
        return 0
    res = list(st.resist or [])
    if "petrified" in c:
        res.append("all")
    if dtype in res or "all" in res:
        dmg = dmg // 2
    vul = st.vulnerable or []
    if dtype in vul:
        dmg = dmg * 2
    return dmg

def harm(ctx, t, dmg, dtype, by, crit, knockout, label):
    # damage after resistance and temporary hp: a body at 0 fails a death save (two on a crit), one that hits 0 drops,
    # and damage of its max hp past 0 kills it outright. A body concentrating saves con or loses the spell.
    st = t.state
    if st.dead:
        return {"dmg": 0}
    dmg = adjust(ctx, t, int(dmg), dtype)
    note = None
    temp = int(st.temp_hp or 0)
    if dmg > 0 and temp > 0:
        soak = min(temp, dmg)
        ctx.patch(t, {"temp_hp": temp - soak})
        dmg = dmg - soak
    if dmg <= 0:
        return {"dmg": 0, "note": "no harm done"}
    hp = int(st.hp or 0)
    mx = int(st.max_hp or 1)
    if st.down and hp <= 0:
        if st.downed_by == "thirst":
            return {"dmg": dmg}
        if dmg >= mx:
            die(ctx, t, "massive damage", by)
            return {"dmg": dmg, "note": "and kills"}
        death_fail(ctx, t, 2 if crit else 1, by)
        return {"dmg": dmg, "note": "and they slip closer to death"}
    left = hp - dmg
    if left <= 0:
        ctx.patch(t, {"hp": 0})
        if -left >= mx and not knockout:
            die(ctx, t, "massive damage", by)
            return {"dmg": dmg, "note": "and kills"}
        drop(ctx, t, by, bool(knockout))
        return {"dmg": dmg, "note": "and they drop" + (", knocked out" if knockout else "")}
    ctx.patch(t, {"hp": left})
    if st.concentrating:
        keep_concentration(ctx, t, dmg)
    return {"dmg": dmg}

def drop(ctx, t, by, knockout):
    # 0 hp: down, unconscious and prone, and dying unless knocked out; a body that dies at zero dies
    who = by.id if by is not None and not isinstance(by, str) else by
    if t.state.dies_at_zero:
        die(ctx, t, "wounds", by)
        return
    if t.state.relentless and not t.state.relentless_used:
        # a half-orc's relentless endurance: once between long rests, 1 hp instead of 0
        ctx.patch(t, {"hp": 1, "relentless_used": True})
        ctx.emit("endured", target=t, reach=1, by=who, hp=1)
        return
    ctx.patch(t, {"hp": 0, "down": True, "downed_by": "wounds", "downed_by_who": who, "dying": not knockout,
                  "stable": bool(knockout), "death_saves": {"s": 0, "f": 0}, "braced": False, "dodging": False,
                  "up_at": (ctx.t + 3600 * ctx.rand.roll("1d4")) if knockout else None})
    end_concentration(ctx, t, "down")
    ctx.emit("downed", target=t, reach=1, by=who, knocked_out=bool(knockout), dying=not knockout)
    if knockout:
        ctx.schedule(float(t.state.up_at) - ctx.t, "come_round", target=t)
    if not knockout and t.parent is not None:
        ensure_fight(ctx, t.parent, t)

def death_fail(ctx, t, n, by):
    ds = dict(t.state.death_saves or {"s": 0, "f": 0})
    ds["f"] = int(ds.get("f") or 0) + n
    ctx.patch(t, {"death_saves": ds, "dying": True, "stable": False, "up_at": None})
    ctx.emit("death_save", target=t, reach=1, roll=None, successes=ds.get("s"), failures=ds["f"], why="struck")
    if ds["f"] >= 3:
        die(ctx, t, "wounds", by)

def die(ctx, t, why, by):
    who = by.id if by is not None and not isinstance(by, str) else (by or t.state.downed_by_who)
    ctx.patch(t, {"dead": True, "hp": 0, "down": True, "dying": False, "stable": False, "death_saves": None, "up_at": None})
    end_concentration(ctx, t, "dead")
    ctx.emit("died", target=t, reach=-1, why=why, by=who)
    if who:
        ctx.emit("killed", target=t, reach=-1, by=who, how=why)

def death_save(ctx, who):
    # at the start of a dying body's turn: 10 or more holds on, 1 is two failures, 20 is back on its feet at 1 hp
    st = who.state
    r = ctx.rand.roll("1d20")
    ds = dict(st.death_saves or {"s": 0, "f": 0})
    if r == 20:
        heal(ctx, who, 1, None, "a death save of 20")
        ctx.emit("death_save", target=who, reach=1, roll=r, successes=0, failures=0, rose=True)
        return "rose"
    if r == 1:
        ds["f"] = int(ds.get("f") or 0) + 2
    elif r >= 10:
        ds["s"] = int(ds.get("s") or 0) + 1
    else:
        ds["f"] = int(ds.get("f") or 0) + 1
    ctx.patch(who, {"death_saves": ds})
    ctx.emit("death_save", target=who, reach=1, roll=r, successes=ds.get("s"), failures=ds.get("f"))
    if int(ds.get("f") or 0) >= 3:
        die(ctx, who, "wounds", st.downed_by_who)
        return "died"
    if int(ds.get("s") or 0) >= 3:
        stabilize(ctx, who, None)
        return "stable"
    return "dying"

def stabilize(ctx, who, by):
    up = ctx.t + 3600 * ctx.rand.roll("1d4")
    ctx.patch(who, {"dying": False, "stable": True, "death_saves": {"s": 0, "f": 0}, "up_at": up})
    ctx.emit("stabilized", target=who, reach=1, by=by.id if by is not None else None, wakes_at=up)
    ctx.schedule(up - ctx.t, "come_round", target=who)

def come_round(ctx, who):
    # a stable body wakes at 1 hp when its 1d4 hours are up (mend's tick checks too, for one made before this timer)
    st = who.state
    if st.down and st.stable and not st.dead and st.up_at is not None and ctx.t >= float(st.up_at):
        heal(ctx, who, 1, None, "came round")

def heal(ctx, t, n, by, why):
    st = t.state
    if st.dead:
        return 0
    hp = int(st.hp or 0)
    mx = int(st.max_hp or 1)
    v = min(mx, hp + max(0, int(n)))
    changes = {"hp": v}
    rose = bool(st.down and v >= 1)
    if rose:
        changes.update({"down": False, "downed_by": None, "downed_by_who": None, "dying": False, "stable": False,
                        "death_saves": None, "up_at": None, "dry_since": None, "fading": None})
    ctx.patch(t, changes)
    ctx.emit("healed", target=t, reach=1, by=by.id if by is not None else None, amount=v - hp, hp=v, why=why)
    if rose:
        ctx.emit("rose", target=t, reach=1, by=by.id if by is not None else "healing")
    return v - hp

# ---- saving throws and concentration ---------------------------------------------------------------------------------

def save(ctx, who, ab, dc, why, tags):
    c = conds(ctx, who)
    if ab in ["str", "dex"]:
        for k in NO_STR_DEX:
            if k in c:
                ctx.emit("saved", target=who, reach=1, ability=ab, dc=dc, roll=None, total=None, success=False, why=why, auto=k)
                return False
    adv = False
    dis = False
    if ab == "dex" and who.state.dodging and not incapacitated(ctx, who):
        adv = True
    if ab == "dex" and "restrained" in c:
        dis = True
    for tag in tags or []:
        if tag in (who.state.save_adv or []):
            adv = True
    r = d20(ctx, adv, dis)
    m = amod(who, ab) + (prof(who) if ab in (who.state.saves or []) else 0) + test_mod(ctx, who) + die_bonus(ctx, who)
    total = r[0] + m
    ok = total >= int(dc)
    ctx.emit("saved", target=who, reach=1, ability=ab, dc=dc, roll=r[0], rolls=r[1], mode=r[2], mod=m, total=total,
             success=ok, why=why)
    return ok

def keep_concentration(ctx, who, dmg):
    dc = min(30, max(10, int(dmg) // 2))
    if not save(ctx, who, "con", dc, "concentration", []):
        end_concentration(ctx, who, "lost")

def end_concentration(ctx, who, why):
    cc = who.state.concentrating
    if not cc:
        return
    for pair in cc.get("conds") or []:
        t = ctx.get(pair[0])
        if t is not None:
            drop_cond(ctx, t, pair[1], "concentration ended")
            for extra in ((t.state.conditions or {}).get(pair[1]) or {}).get("also") or []:
                drop_cond(ctx, t, extra, "concentration ended")
    ctx.patch(who, {"concentrating": None})
    ctx.emit("concentration_ended", target=who, reach=1, spell=cc.get("spell"), why=why)

# ---- spells ----------------------------------------------------------------------------------------------------------

def spell_of(ctx, who, name):
    n = str(name or "").strip().lower()
    cat = ctx.root().state.spells or {}
    own = (who.state.spellcasting or {}).get("own") or {}
    e = cat.get(n)
    if own.get(n):
        e = dict(e or {})
        e.update(own.get(n))
    return e

def knows(who, name):
    sc = who.state.spellcasting or {}
    return str(name or "").strip().lower() in [str(x).lower() for x in (sc.get("spells") or [])]

def lowest_slot(who, at_least):
    slots = (who.state.spellcasting or {}).get("slots") or {}
    for lv in range(int(at_least), 10):
        if int(slots.get(str(lv)) or 0) > 0:
            return lv
    return None

def spend_slot(ctx, who, lv):
    sc = dict(who.state.spellcasting or {})
    slots = dict(sc.get("slots") or {})
    slots[str(lv)] = max(0, int(slots.get(str(lv)) or 0) - 1)
    sc["slots"] = slots
    ctx.patch(who, {"spellcasting": {"slots": slots}})

def cast_mod(who):
    return amod(who, (who.state.spellcasting or {}).get("ability") or "int")

def save_dc(who):
    return 8 + prof(who) + cast_mod(who)

def caster_level(who):
    return int(who.state.level or who.state.cr or 1)

def upcast(dice, extra, times):
    # dice plus `times` more of `extra` ("3d6" + 2 x "1d6" = "5d6", when they are the same die)
    if not extra or times <= 0:
        return dice
    a = str(dice).split("+")
    b = str(extra).split("+")
    da = a[0].split("d")
    db = b[0].split("d")
    if len(da) == 2 and len(db) == 2 and da[1] == db[1]:
        out = str(int(da[0] or 1) + int(db[0] or 1) * times) + "d" + da[1]
        if len(a) > 1:
            out = out + "+" + a[1]
        return out
    return dice

def area_targets(ctx, me, t, sp):
    out = [t]
    if not sp.get("area") or t.parent is None:
        return out
    for p in ctx.children(t.parent, "creature"):
        if p.id == t.id or p.id == me.id or p.state.dead or p.state.hidden:
            continue
        if sp.get("target") == "ally":
            if not at_odds(ctx, me, p):
                out.append(p)
        elif at_odds(ctx, me, p) or at_odds(ctx, p, me):
            out.append(p)
    return out

def harmful_spell(sp):
    return sp is not None and sp.get("kind") in ["attack", "save", "auto"]

def cast_spell(ctx, me, t, name, sp, lv):
    # one casting: the slot, concentration, then what the spell does to each target
    if int(sp.get("level") or 0) > 0:
        spend_slot(ctx, me, lv)
    if sp.get("conc"):
        end_concentration(ctx, me, "a new spell")
    if harmful_spell(sp):
        for x in area_targets(ctx, me, t, sp):
            provoke(ctx, me, x)
            mark_foes(ctx, me, x)
    if "hidden" in conds(ctx, me) and harmful_spell(sp):
        drop_cond(ctx, me, "hidden", "cast")
    ctx.emit("cast", target=t, reach=1, by=me.id, spell=name, level=lv, at=t.id)
    above = max(0, int(lv) - int(sp.get("level") or 0))
    kind = sp.get("kind")
    out = {"spell": name, "level": lv, "results": []}
    kept = []
    if kind == "attack":
        n = int(sp.get("rays") or 1) + int(sp.get("upcast_rays") or 0) * above
        dice = sp.get("dice")
        if int(sp.get("level") or 0) == 0:
            if sp.get("beams"):
                n = 1 + (1 if caster_level(me) >= 5 else 0) + (1 if caster_level(me) >= 11 else 0) + (1 if caster_level(me) >= 17 else 0)
            else:
                dice = scale_cantrip(dice, caster_level(me))
        dice = upcast(dice, sp.get("upcast"), above)
        for i in range(n):
            if t.state.dead:
                break
            r = spell_attack(ctx, me, t, name, dice, sp)
            out["results"].append(r)
            if r.get("hit") and sp.get("cond"):
                if put_cond(ctx, me, t, sp, name):
                    kept.append([t.id, sp["cond"]["name"]])
    elif kind == "auto":
        darts = int(sp.get("darts") or 1) + above
        total = 0
        for i in range(darts):
            total = total + roll_dice(ctx, sp.get("dice"), False)
        res = harm(ctx, t, total, sp.get("dtype"), me, False, False, name)
        ctx.emit("hit", target=t, reach=1, by=me.id, dmg=res["dmg"], rolled=total, dtype=sp.get("dtype"), weapon=name,
                 spell=name, hp=t.state.hp, ranged=True)
        out["results"].append({"hit": True, "dmg": res["dmg"]})
        ctx.log(name + ": " + str(darts) + " darts, " + str(res["dmg"]) + " " + str(sp.get("dtype")))
    elif kind == "save":
        dc = save_dc(me)
        dice = sp.get("dice")
        rolled = None
        for x in area_targets(ctx, me, t, sp):
            d = dice
            if sp.get("hurt_dice") and int(x.state.hp or 0) < int(x.state.max_hp or 0):
                d = sp.get("hurt_dice")
            if d and int(sp.get("level") or 0) == 0:
                d = scale_cantrip(d, caster_level(me))
            if d:
                d = upcast(d, sp.get("upcast"), above)
            tags = ["charmed"] if (sp.get("cond") or {}).get("name") == "charmed" else []
            ok = save(ctx, x, sp.get("save"), dc, name, tags)
            dmg = 0
            if d:
                if rolled is None or not sp.get("area"):
                    rolled = roll_dice(ctx, d, False)
                dmg = rolled if not ok else (rolled // 2 if sp.get("half") else 0)
                if dmg > 0:
                    res = harm(ctx, x, dmg, sp.get("dtype"), me, False, False, name)
                    ctx.emit("hit", target=x, reach=1, by=me.id, dmg=res["dmg"], rolled=dmg, dtype=sp.get("dtype"),
                             weapon=name, spell=name, saved=ok, dc=dc, hp=x.state.hp)
                    dmg = res["dmg"]
                else:
                    ctx.emit("missed", target=x, reach=1, by=me.id, weapon=name, spell=name, saved=ok, dc=dc)
            if not ok and sp.get("cond") and not x.state.dead:
                if put_cond(ctx, me, x, sp, name):
                    kept.append([x.id, sp["cond"]["name"]])
            out["results"].append({"target": x.id, "saved": ok, "dmg": dmg})
            ctx.log(name + " on " + x.name + ": " + str(sp.get("save")) + " save vs DC " + str(dc) + (" saved" if ok else " failed")
                    + (", " + str(dmg) + " " + str(sp.get("dtype")) if d else ""))
    elif kind == "heal":
        dice = upcast(sp.get("dice"), sp.get("upcast"), above)
        for x in area_targets(ctx, me, t, sp):
            n = roll_dice(ctx, dice, False) + (cast_mod(me) if sp.get("add_mod") else 0)
            got = heal(ctx, x, n, me, name)
            out["results"].append({"target": x.id, "healed": got})
            ctx.log(name + " on " + x.name + ": " + str(got) + " hp")
    elif kind == "buff":
        for x in area_targets(ctx, me, t, sp):
            if put_cond(ctx, me, x, sp, name):
                kept.append([x.id, sp["cond"]["name"]])
        ctx.log(name + " on " + t.name)
    if sp.get("conc") and kept:
        ctx.patch(me, {"concentrating": {"spell": name, "conds": kept, "since": ctx.t}})
    return out

def put_cond(ctx, me, x, sp, name):
    src = sp.get("cond") or {}
    nm = src.get("name")
    c = {}
    for k, v in src.items():
        if k != "name" and v is not None:
            c[k] = v
    c["by"] = me.id
    c["spell"] = name
    if c.get("save"):
        c["save"] = {"ability": c.get("save"), "dc": save_dc(me)}
    if c.get("escape"):
        c["escape"] = {"ability": c.get("escape"), "dc": save_dc(me)}
    if c.get("rounds") is not None and not x.state.fight:
        c["until"] = ctx.t + 6 * int(c.get("rounds"))
        c.pop("rounds")
    return add_cond(ctx, x, nm, c)

def spell_attack(ctx, me, t, name, dice, sp):
    ranged = sp.get("attack") == "ranged"
    mode = attack_mode(ctx, me, t, ranged)
    r = d20(ctx, len(mode[0]) > 0, len(mode[1]) > 0)
    nat = r[0]
    b = prof(me) + cast_mod(me) + test_mod(ctx, me) + die_bonus(ctx, me)
    total = nat + b
    ac = armor_class(ctx, t) + (cover(t.parent) if ranged else 0)
    crit = nat == 20
    hit = nat != 1 and (crit or total >= ac)
    use_once(ctx, me, ["helped", "mocked"])
    if hit and not crit and try_shield(ctx, t, total, ac):
        hit = False
        ac = ac + 5
    if not hit:
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon=name, spell=name, attack=total, ac=ac, rolls=r[1], mode=r[2])
        ctx.log(name + ": d20 " + str(nat) + " + " + str(b) + " = " + str(total) + " vs AC " + str(ac) + ": miss")
        return {"hit": False}
    use_once(ctx, t, ["guided"])
    dmg = roll_dice(ctx, dice, crit)
    res = harm(ctx, t, dmg, sp.get("dtype"), me, crit, False, name)
    ctx.emit("hit", target=t, reach=1, by=me.id, dmg=res["dmg"], rolled=dmg, dtype=sp.get("dtype"), weapon=name, spell=name,
             attack=total, ac=ac, rolls=r[1], mode=r[2], crit=crit, hp=t.state.hp, ranged=ranged)
    ctx.log(name + ": d20 " + str(nat) + " + " + str(b) + " = " + str(total) + " vs AC " + str(ac) + ": "
            + ("CRIT, " if crit else "hit, ") + str(res["dmg"]) + " " + str(sp.get("dtype")))
    return {"hit": True, "dmg": res["dmg"], "crit": crit}

# ---- the fight -------------------------------------------------------------------------------------------------------

def fight_in(ctx, place):
    if place is None:
        return None
    for f in ctx.children(place, "fight"):
        return f
    return None

def my_fight(ctx, who):
    # the fight this body is in, where it stands; None when it is in none
    f = ctx.get(who.state.fight) if who.state.fight else None
    if f is None or who.parent is None or f.parent is None or f.parent.id != who.parent.id:
        return None
    return f

def eligible(p):
    return p.state.hp is not None and not p.state.dead and not p.state.hidden

def init_mod(ctx, p):
    return amod(p, "dex") + int(p.state.init_bonus or 0) + test_mod(ctx, p)

def signed(n):
    return ("+" if n >= 0 else "") + str(n)

def init_roll(ctx, p):
    surprised = bool(p.state.asleep)
    r = d20(ctx, bool(p.state.init_adv), surprised)
    return init_entry(ctx, p, r[0])

def init_entry(ctx, p, face):
    return {"id": p.id, "name": p.name, "init": int(face) + init_mod(ctx, p), "dex": score(p, "dex"), "roll": int(face),
            "surprised": bool(p.state.asleep)}

def rolls_own(ctx, p):
    # a body someone plays rolls its own initiative (the player's own d20, or the world's on their word), unless the
    # world turned that off (the root's dnd5e.player_rolls false)
    return is_held(ctx, p) and settings(ctx).get("player_rolls") is not False

def to_roll(ctx, p):
    # an order entry still waiting on its initiative
    return {"id": p.id, "name": p.name, "init": None, "dex": score(p, "dex"), "roll": None, "surprised": bool(p.state.asleep),
            "rolling": True}

def roll_call(ctx, p):
    # what a body that rolls its own is told: its die and what it adds
    return (p.name + ": d20 " + signed(init_mod(ctx, p))
            + (", two dice keeping the lower (surprised)" if p.state.asleep else "")
            + (", two dice keeping the higher" if p.state.init_adv and not p.state.asleep else ""))

def waiting_on(ctx, f):
    return [name_of(ctx, i) for i in (f.state.rolling or [])]

def order_key(ctx, e):
    p = ctx.get(e["id"])
    return [-int(e["init"]), -int(e.get("dex") or 10), 1 if (p is not None and is_held(ctx, p)) else 0, str(e["name"]), e["id"]]

def sort_order(ctx, entries):
    keyed = [[order_key(ctx, e), i] for i, e in enumerate(entries)]
    keyed = sorted(keyed)
    return [entries[k[1]] for k in keyed]

def start_fight(ctx, place, by, against):
    # the first hostile deed here: everyone living rolls initiative. Bodies nobody plays roll at once; a played body
    # rolls its own (roll_initiative: the player's d20, or the world's on their word), and the order is set and the first
    # turn opens once every roll is in (begin_fight), or when the wait runs out and the world rolls for the rest
    f = fight_in(ctx, place)
    if f is not None:
        if by is not None and against is not None:
            mark_foes(ctx, by, against)
        return f
    entries = []
    waiting = []
    for p in ctx.children(place, "creature"):
        if not eligible(p):
            continue
        if by is not None and rolls_own(ctx, p):
            waiting.append(p)
            entries.append(to_roll(ctx, p))
        else:
            entries.append(init_roll(ctx, p))
    foes = {}
    if by is not None and against is not None:
        foes[by.id] = [against.id]
        foes[against.id] = [by.id]
    f = ctx.spawn("fight", place, "Fight", state={"order": entries, "turn": 0, "round": 1, "foes": foes, "started": ctx.t,
                                                   "by": by.id if by is not None else None, "calm": 0, "hostile": True,
                                                   "rolling": [p.id for p in waiting] if waiting else None})
    for e in entries:
        ctx.patch(e["id"], {"fight": f.id, "initiative": e["init"], "turn": None})
    if waiting:
        ctx.emit("roll_initiative", target=place, reach=1, by=by.id, waiting=[p.id for p in waiting],
                 text="Roll initiative! " + "; ".join([roll_call(ctx, p) for p in waiting])
                      + ". Roll your own d20 and give what it shows (initiative, roll), or let the world roll (initiative)")
        ctx.schedule(held_wait(ctx), "fight_next", target=place, payload={"fight": f.id, "round": 1, "turn": 0, "why": "roll"})
        return ctx.get(f.id)
    return begin_fight(ctx, f, by)

def begin_fight(ctx, f, starter):
    # every initiative is in: the order is set and the first turn opens. starter is the body whose deed opened the fight
    # when it is about to act at once (its caller takes that turn); None when the turns are the fight's own to run
    order = sort_order(ctx, [e for e in (f.state.order or []) if e.get("init") is not None])
    ctx.patch(f, {"order": order, "turn": 0, "rolling": None})
    f = ctx.get(f.id)
    if not order:
        end_fight(ctx, f, "nobody left")
        return None
    for e in order:
        ctx.patch(e["id"], {"initiative": e["init"]})
    ctx.emit("initiative", target=f.parent, reach=1, by=f.state.by,
             order=[{"id": e["id"], "name": e["name"], "init": e["init"], "roll": e["roll"], "surprised": e["surprised"]} for e in order],
             text="Initiative: " + ", ".join([e["name"] + " " + str(e["init"]) for e in order]))
    r = open_turn(ctx, f, 0)
    if r == "skip" or (r == "npc" and (starter is None or order[0]["id"] != starter.id)):
        schedule_next(ctx, f, r)  # the first turn is someone else's: it is taken a moment from now
    return ctx.get(f.id)

def set_initiative(ctx, f, who, face):
    # a played body's initiative: face is what its player's own d20 showed, or None and the world rolls it
    e = init_roll(ctx, who) if face is None else init_entry(ctx, who, face)
    order = [e if x["id"] == who.id else x for x in (f.state.order or [])]
    ctx.patch(f, {"order": order, "rolling": [i for i in (f.state.rolling or []) if i != who.id]})
    ctx.patch(who, {"initiative": e["init"]})
    ctx.emit("rolled_initiative", target=f.parent, reach=1, who=who.id, roll=e["roll"], init=e["init"],
             by_world=face is None,
             text=who.name + (" rolls " if face is None else "'s own die shows ") + str(e["roll"]) + " " + signed(init_mod(ctx, who))
                  + ": initiative " + str(e["init"]))
    return e

def world_rolls_rest(ctx, f):
    # the wait ran out: the world rolls for whoever has not, and the fight begins
    for i in list(f.state.rolling or []):
        p = ctx.get(i)
        if p is not None:
            set_initiative(ctx, ctx.get(f.id), p, None)
    return begin_fight(ctx, ctx.get(f.id), None)

def ensure_fight(ctx, place, who):
    # a dying body needs its turns for its death saves: it gets a fight if none is on here
    f = fight_in(ctx, place)
    if f is None:
        return start_fight(ctx, place, None, None)
    if not who.state.fight:
        join_fight(ctx, f, who)
    return f

def mark_foes(ctx, a, b):
    f = ctx.get(a.state.fight) if a.state.fight else None
    if f is None or b.id == a.id:
        return
    foes = dict(f.state.foes or {})
    for pair in [[a.id, b.id], [b.id, a.id]]:
        lst = list(foes.get(pair[0]) or [])
        if pair[1] not in lst:
            lst.append(pair[1])
        foes[pair[0]] = lst
    ctx.patch(f, {"foes": foes, "hostile": True})

def join_fight(ctx, f, p):
    if not eligible(p):
        return
    order = list(f.state.order or [])
    for e in order:
        if e["id"] == p.id and not e.get("gone"):
            return
    order = [x for x in order if x["id"] != p.id]
    if f.state.rolling:
        # initiative is still being rolled: a played body that walks in rolls its own too; the order is sorted at the start
        own = rolls_own(ctx, p)
        e = to_roll(ctx, p) if own else init_roll(ctx, p)
        ctx.patch(f, {"order": order + [e], "rolling": list(f.state.rolling) + ([p.id] if own else [])})
        ctx.patch(p, {"fight": f.id, "initiative": e["init"], "turn": None})
        if own:
            ctx.emit("joined_fight", target=f.parent, reach=1, who=p.id, init=None, roll=None,
                     text="Roll initiative! " + roll_call(ctx, p))
        else:
            ctx.emit("joined_fight", target=f.parent, reach=1, who=p.id, init=e["init"], roll=e["roll"])
        return
    e = init_roll(ctx, p)
    cur = f.state.turn_of
    k = order_key(ctx, e)
    at = len(order)
    for i, x in enumerate(order):
        if k < order_key(ctx, x):
            at = i
            break
    order = order[:at] + [e] + order[at:]
    turn = int(f.state.turn or 0)
    for i, x in enumerate(order):
        if x["id"] == cur:
            turn = i
    ctx.patch(f, {"order": order, "turn": turn})
    ctx.patch(p, {"fight": f.id, "initiative": e["init"], "turn": None})
    ctx.emit("joined_fight", target=f.parent, reach=1, who=p.id, init=e["init"], roll=e["roll"])

def leave_fight(ctx, f, p, why):
    if f.state.rolling:
        # gone before the order was set: out of it, and the fight begins if they were the last it waited on
        rolling = [i for i in f.state.rolling if i != p.id]
        ctx.patch(f, {"order": [x for x in (f.state.order or []) if x["id"] != p.id], "rolling": rolling})
        ctx.patch(p, {"fight": None, "initiative": None, "turn": None, "dodging": False, "disengaged": False, "declared": None})
        if not rolling:
            begin_fight(ctx, ctx.get(f.id), None)
        return
    order = list(f.state.order or [])
    for i, e in enumerate(order):
        if e["id"] == p.id:
            e = dict(e)
            e["gone"] = True
            order[i] = e
    ctx.patch(f, {"order": order})
    ctx.patch(p, {"fight": None, "initiative": None, "turn": None, "dodging": False, "disengaged": False, "declared": None})
    if f.state.turn_of == p.id:
        schedule_next(ctx, f, "left")

def held_wait(ctx):
    return float(settings(ctx).get("turn_wait") or 120)

def schedule_next(ctx, f, why):
    ctx.schedule(float(settings(ctx).get("npc_gap") or 0.5), "fight_next", target=f.parent,
                 payload={"fight": f.id, "round": f.state.round, "turn": f.state.turn, "why": why})

def open_turn(ctx, f, idx):
    # the start of a turn: the economy back, a dodge or a disengage over, start-of-turn marks off, a dying body's death
    # save. Returns "wait" (a played body: its turn waits for it), "npc" (taken at once by the caller) or "skip".
    order = f.state.order or []
    e = order[idx]
    who = ctx.get(e["id"])
    ctx.patch(f, {"turn": idx, "turn_of": e["id"], "turn_t": ctx.t})
    if who is None or e.get("gone") or who.state.dead or who.parent is None or who.parent.id != f.parent.id:
        return "skip"
    econ = {"action": 1, "bonus": 1, "move": 1, "reaction": 1, "attacks": 0}
    ctx.patch(who, {"turn": econ, "dodging": False, "disengaged": False, "sneak_used": None})
    tick_conditions(ctx, who, "start")
    if who.state.down and who.state.dying and who.state.downed_by != "thirst":
        death_save(ctx, who)
        return "skip"
    if incapacitated(ctx, who):
        return "skip"
    if is_held(ctx, who):
        ctx.emit("turn", target=f.parent, reach=1, who=who.id, round=f.state.round, initiative=e["init"],
                 hp=who.state.hp, ac=armor_class(ctx, who), text="Round " + str(f.state.round) + ": " + who.name + "'s turn")
        if who.state.declared:
            take_declared(ctx, f, who)
            return "wait"
        ctx.schedule(held_wait(ctx), "fight_next", target=f.parent,
                     payload={"fight": f.id, "round": f.state.round, "turn": idx, "why": "wait"})
        return "wait"
    return "npc"

def take_declared(ctx, f, who):
    # a deed declared before initiative was rolled lands when its turn comes
    d = who.state.declared or {}
    ctx.patch(who, {"declared": None})
    t = ctx.get(d.get("target"))
    verb = d.get("verb") or "attack"
    if t is None or not upright(t) or t.parent is None or who.parent is None:
        return
    if verb != "shoot" and t.parent.id != who.parent.id:
        return
    pay(ctx, who, "attack", verb)
    deed5(ctx, who, verb, t, d.get("params") or {})
    if turn_done(ctx, who, verb):
        schedule_next(ctx, f, "done")

def can_strike(ctx, me, t):
    # why a blow (or a grapple, a shove) at them cannot be struck now, or None
    if t.id == me.id:
        return "you would not"
    if t.parent is None or me.parent is None or t.parent.id != me.parent.id:
        return "they are not here"
    if me.state.dead:
        return "the dead do not fight"
    if me.state.down:
        return "you are down"
    if incapacitated(ctx, me):
        return "you cannot act: " + ", ".join([k for k in conds(ctx, me) if k in INCAP])
    if t.state.dead:
        return "they are dead"
    if t.state.down:
        return "they are down: kill them, or spare them"
    if me.state.yielded == t.id:
        return "you yielded to them"
    return ring_blocks(ctx, me, t)

def deed5(ctx, me, verb, t, p):
    if verb == "shoot":
        w = ranged(me)
        if w is None or can_fire(me, w) is not None:
            return {"hit": False, "why": "nothing to shoot with"}
        return fire(ctx, me, t, w)
    if verb == "grapple":
        return grapple5(ctx, me, t)
    if verb == "shove":
        return shove5(ctx, me, t)
    return strike5(ctx, me, t, melee_weapon(me, p.get("with")), {"knockout": bool(p.get("knockout"))})

def open_with(ctx, verb):
    # the deed in a fight: start one if none is on here; if someone else's turn comes first, declare the deed
    me = ctx.actor
    t = ctx.target
    p = ctx.params or {}
    f = my_fight(ctx, me)
    started = False
    if f is None and t.parent is not None and t.parent.id == me.parent.id:
        f = start_fight(ctx, me.parent, me, t)
        started = True
        if f.state.rolling:
            ctx.patch(me, {"declared": {"verb": verb, "target": t.id, "params": p}})
            ctx.log(rolling_line(ctx, f, me) + ". Your " + verb + " lands when your turn comes")
            return {"waiting": True, "roll_initiative": waiting_on(ctx, f)}
        if f.state.turn_of != me.id:
            ctx.patch(me, {"declared": {"verb": verb, "target": t.id, "params": p}})
            ctx.log("initiative: " + order_text(ctx, f) + ". You act after " + ", ".join(ahead_of(f, me))
                    + ": your " + verb + " lands when your turn comes")
            return {"waiting": True, "initiative": order_text(ctx, f)}
        pay(ctx, me, "attack", verb)
    r = deed5(ctx, me, verb, t, p)
    if started:
        r["initiative"] = order_text(ctx, f)
        ctx.log("initiative: " + order_text(ctx, f))
        if turn_done(ctx, me, verb):
            schedule_next(ctx, f, "done")
    return r

def rolling_line(ctx, f, me):
    # what the one who opened a fight is told while initiative is rolled
    if me.id in (f.state.rolling or []):
        return ("Roll initiative! Your d20 " + signed(init_mod(ctx, me))
                + ": roll your own and give what it shows (initiative, roll), or let the world roll (initiative)")
    return "Roll initiative! Waiting on " + ", ".join(waiting_on(ctx, f))

def ahead_of(f, who):
    out = []
    for e in f.state.order or []:
        if e["id"] == who.id:
            break
        if not e.get("gone"):
            out.append(e["name"])
    return out

def grip_dc(who):
    return 8 + amod(who, "str") + prof(who)

def better_save(who):
    return "str" if amod(who, "str") + (prof(who) if "str" in (who.state.saves or []) else 0) >= amod(who, "dex") + (prof(who) if "dex" in (who.state.saves or []) else 0) else "dex"

def grapple5(ctx, me, t):
    # one of your attacks: they save str or dex (their better) against 8 + your str + proficiency, or you hold them
    provoke(ctx, me, t)
    mark_foes(ctx, me, t)
    dc = grip_dc(me)
    ok = save(ctx, t, better_save(t), dc, "grapple", [])
    if ok:
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon="grapple", dc=dc, saved=True)
        ctx.log("grapple: " + t.name + " slips free (save vs " + str(dc) + ")")
        return {"hit": False, "dc": dc}
    add_cond(ctx, t, "grappled", {"by": me.id, "escape": {"ability": "str", "dc": dc}})
    ctx.emit("grappled", target=t, reach=1, by=me.id, dc=dc)
    ctx.log("grapple: you have " + t.name + " (escape against " + str(dc) + ")")
    return {"hit": True, "dc": dc}

def shove5(ctx, me, t):
    provoke(ctx, me, t)
    mark_foes(ctx, me, t)
    dc = grip_dc(me)
    ok = save(ctx, t, better_save(t), dc, "shove", [])
    if ok:
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon="shove", dc=dc, saved=True)
        ctx.log("shove: " + t.name + " keeps their feet (save vs " + str(dc) + ")")
        return {"hit": False, "dc": dc}
    add_cond(ctx, t, "prone", {"by": me.id})
    ctx.emit("shoved", target=t, reach=1, by=me.id, dc=dc)
    ctx.log("shove: " + t.name + " goes down prone")
    return {"hit": True, "dc": dc}

def tick_conditions(ctx, who, when):
    # rounds count down at the end (or start, for those that say so) of the bearer's turn; a save rolled again ends one
    for k, e in (who.state.conditions or {}).items():
        if e is None or not isinstance(e, dict):
            continue
        if when == "end" and e.get("save"):
            sv = e.get("save")
            if save(ctx, who, sv.get("ability"), sv.get("dc"), k, []):
                drop_cond(ctx, who, k, "saved")
                continue
        if e.get("rounds") is None or (e.get("ends") or "end") != when:
            continue
        n = int(e.get("rounds")) - 1
        if n <= 0:
            drop_cond(ctx, who, k, "ran out")
        else:
            e2 = dict(e)
            e2["rounds"] = n
            ctx.patch(who, {"conditions": {k: e2}})
    if when == "end":
        drop_cond(ctx, who, "mocked", "ran out")

def close_turn(ctx, f):
    who = ctx.get(f.state.turn_of) if f.state.turn_of else None
    if who is not None and not who.state.dead and who.state.fight == f.id:
        tick_conditions(ctx, who, "end")
        if who.state.concentrating and incapacitated(ctx, who):
            end_concentration(ctx, who, "incapacitated")

def fight_live(ctx, f):
    # still a fight: two standing bodies here at odds, or someone dying
    ms = []
    for e in f.state.order or []:
        p = ctx.get(e["id"])
        if p is not None and not e.get("gone") and p.parent is not None and p.parent.id == f.parent.id:
            ms.append(p)
    for p in ms:
        if p.state.down and p.state.dying and not p.state.dead and p.state.downed_by != "thirst":
            return True
    for a in ms:
        if not upright(a):
            continue
        for b in ms:
            if b.id != a.id and upright(b) and at_odds(ctx, a, b):
                return True
    return False

def end_fight(ctx, f, why):
    place = f.parent
    for e in f.state.order or []:
        p = ctx.get(e["id"])
        if p is None or p.state.fight != f.id:
            continue
        changes = {"fight": None, "initiative": None, "turn": None, "dodging": False, "disengaged": False, "declared": None}
        conds2 = {}
        for k, c in (p.state.conditions or {}).items():
            if isinstance(c, dict) and c.get("rounds") is not None:
                c2 = dict(c)
                c2["until"] = ctx.t + 6 * int(c.get("rounds"))
                c2["rounds"] = None
                conds2[k] = c2
        if conds2:
            changes["conditions"] = conds2
        ctx.patch(p, changes)
    ctx.emit("fight_over", target=place, reach=1, rounds=f.state.round, why=why)
    ctx.destroy(f)

def advance(ctx, f, budget):
    # end the turn that is on and open the next, taking the turns of bodies nobody plays at once, until a played body's
    # turn waits for it, the fight is over, or the budget is spent (then a timer carries on)
    n = 0
    while n < budget:
        f = ctx.get(f.id)
        if f is None:
            return
        close_turn(ctx, f)
        order = f.state.order or []
        idx = int(f.state.turn or 0) + 1
        if idx >= len(order):
            if not fight_live(ctx, f):
                end_fight(ctx, f, "calm")
                return
            keep = [e for e in order if not e.get("gone") and ctx.get(e["id"]) is not None and not ctx.get(e["id"]).state.dead]
            if not keep:
                end_fight(ctx, f, "nobody left")
                return
            ctx.patch(f, {"order": keep, "round": int(f.state.round or 1) + 1, "turn": 0, "hostile": False})
            f = ctx.get(f.id)
            idx = 0
        nxt = ctx.get((f.state.order or [])[idx]["id"])
        if nxt is not None and is_held(ctx, nxt) and not fight_live(ctx, f):
            end_fight(ctx, f, "calm")  # nobody at odds is left standing: no played turn opens on an empty fight
            return
        r = open_turn(ctx, f, idx)
        n = n + 1
        if r == "wait":
            return
        if r == "npc":
            who = ctx.get(f.state.turn_of)
            npc_turn(ctx, f, who)
    f = ctx.get(f.id)
    if f is not None:
        schedule_next(ctx, f, "more")

# ---- what a turn costs -----------------------------------------------------------------------------------------------

def cost_of(ctx, who, verb, target, params):
    if verb == "cast":
        sp = spell_of(ctx, who, (params or {}).get("spell"))
        return (sp or {}).get("time") or "action"
    if verb == "drink" and target is not None and target.state.heals:
        return "bonus"
    table = dict(DEFAULT_COSTS)
    table.update(settings(ctx).get("costs") or {})
    return table.get(verb) or "action"

def attacks_per_action(who):
    return 1 + int(who.state.extra_attacks or 0)

def pay_check(ctx, who, cost, verb):
    # why this deed cannot be paid for now, or None: the turn's action, bonus action, move or attacks
    econ = who.state.turn or {}
    if cost == "attack":
        if int(econ.get("attacks") or 0) > 0 or int(econ.get("action") or 0) > 0:
            return None
        return "you have used your action this turn"
    if cost == "action":
        if int(econ.get("action") or 0) > 0:
            return None
        if verb in CUNNING and who.state.cunning and int(econ.get("bonus") or 0) > 0:
            return None
        return "you have used your action this turn"
    if cost == "bonus":
        if int(econ.get("bonus") or 0) > 0:
            return None
        return "you have used your bonus action this turn"
    if cost == "move":
        if int(econ.get("move") or 0) > 0:
            return None
        return "you have used your movement this turn"
    if cost == "reaction":
        return None if can_react(ctx, who) else "you have used your reaction"
    return None

def pay(ctx, who, cost, verb):
    econ = dict(who.state.turn or {"action": 1, "bonus": 1, "move": 1, "reaction": 1, "attacks": 0})
    if cost == "attack":
        if int(econ.get("attacks") or 0) > 0:
            econ["attacks"] = int(econ["attacks"]) - 1
        else:
            econ["action"] = 0
            econ["attacks"] = attacks_per_action(who) - 1
    elif cost == "action":
        if int(econ.get("action") or 0) > 0:
            econ["action"] = 0
        elif verb in CUNNING and who.state.cunning:
            econ["bonus"] = 0
        if verb == "dash":
            econ["move"] = int(econ.get("move") or 0) + 1
    elif cost == "bonus":
        econ["bonus"] = 0
    elif cost == "move":
        econ["move"] = max(0, int(econ.get("move") or 0) - 1)
    elif cost == "reaction":
        econ["reaction"] = 0
    ctx.patch(who, {"turn": econ})
    return econ

def bonus_options(ctx, who):
    # what this body could still do with a bonus action: an offhand blow, a bonus spell, a potion, a rogue's cunning
    out = []
    ws = [it for it in held_things(who) if it.state.weapon and not it.state.ranged]
    if len(ws) >= 2 and "light" in props(ws[1]):
        out.append("offhand")
    sc = who.state.spellcasting or {}
    for n in sc.get("spells") or []:
        sp = spell_of(ctx, who, n)
        if sp is not None and sp.get("time") == "bonus" and (int(sp.get("level") or 0) == 0 or lowest_slot(who, sp.get("level")) is not None):
            out.append("cast " + str(n))
    for it in held_things(who):
        if it.state.heals and int(it.state.doses or 1) > 0:
            out.append("drink " + it.name)
            break
    if who.state.cunning:
        out.append("dash, disengage or hide")
    return out

def turn_done(ctx, who, verb):
    # the turn ends itself once the action is spent and nothing is left for a bonus action (dash and disengage leave
    # the move to be made)
    if verb in ["dash", "disengage"]:
        return False
    econ = who.state.turn or {}
    if int(econ.get("action") or 0) > 0 or int(econ.get("attacks") or 0) > 0:
        return False
    if int(econ.get("bonus") or 0) > 0 and bonus_options(ctx, who):
        return False
    return True

def turn_left(ctx, who):
    econ = who.state.turn or {}
    out = []
    if int(econ.get("attacks") or 0) > 0:
        out.append(str(econ.get("attacks")) + " more attack" + ("s" if int(econ.get("attacks")) > 1 else ""))
    if int(econ.get("action") or 0) > 0:
        out.append("an action")
    if int(econ.get("bonus") or 0) > 0:
        out.append("a bonus action")
    if int(econ.get("move") or 0) > 0:
        out.append("your move")
    return out

def order_text(ctx, f):
    out = []
    for e in f.state.order or []:
        if e.get("gone"):
            continue
        if e.get("init") is None:
            out.append(e["name"] + " (rolling)")
            continue
        out.append(e["name"] + " " + str(e["init"]) + (" (now)" if e["id"] == f.state.turn_of else ""))
    return ", ".join(out)

# ---- a body nobody plays, on its turn --------------------------------------------------------------------------------

def foe_for(ctx, f, me):
    # whom it fights: inside a duel, the other one; else whoever struck it last, then anyone at odds with it here
    if me.parent is None:
        return None
    for d in ctx.relations(me, "duel"):
        for pid in d["participants"]:
            o = ctx.get(pid)
            if pid != me.id and upright(o) and o.parent.id == me.parent.id:
                return o
        return None
    if me.state.fights is False:
        return None
    last = ctx.get(me.state.attacked_by) if me.state.attacked_by else None
    if upright(last) and last.parent.id == me.parent.id and at_odds(ctx, me, last) and not in_ring(ctx, last):
        return last
    for e in f.state.order or []:
        p = ctx.get(e["id"])
        if p is not None and not e.get("gone") and upright(p) and p.parent.id == me.parent.id and at_odds(ctx, me, p) and not in_ring(ctx, p):
            return p
    return None

def in_ring(ctx, who):
    return len(ctx.relations(who, "duel")) > 0

def best_spell(ctx, me, t):
    # the strongest harmful spell it can cast now: the highest slot it has, else a cantrip
    sc = me.state.spellcasting or {}
    best = None
    best_lv = -1
    for n in sc.get("spells") or []:
        sp = spell_of(ctx, me, n)
        if sp is None or not harmful_spell(sp) or (sp.get("time") or "action") != "action":
            continue
        lv = int(sp.get("level") or 0)
        at = lv if lv == 0 else lowest_slot(me, lv)
        if at is None:
            continue
        if lv > best_lv:
            best = [n, sp, at]
            best_lv = lv
    return best

def heal_spell(ctx, me):
    sc = me.state.spellcasting or {}
    for n in sc.get("spells") or []:
        sp = spell_of(ctx, me, n)
        if sp is not None and sp.get("kind") == "heal" and lowest_slot(me, sp.get("level") or 1) is not None:
            return [n, sp, lowest_slot(me, sp.get("level") or 1)]
    return None

def npc_turn(ctx, f, me):
    # a body nobody plays: up off the floor, a downed friend healed if it can, then at its foe with spell, blade or bow
    if me is None or not upright(me) or incapacitated(ctx, me):
        return
    if me.state.declared:
        ctx.patch(me, {"declared": None})
    if "prone" in conds(ctx, me) and not me.state.down:
        drop_cond(ctx, me, "prone", "stood")
        pay(ctx, me, "move", "stand")
    hs = heal_spell(ctx, me)
    if hs is not None and me.state.faction:
        for p in ctx.children(me.parent, "creature"):
            if p.id != me.id and p.state.down and p.state.dying and not p.state.dead and p.state.faction == me.state.faction:
                cast_spell(ctx, me, p, hs[0], hs[1], hs[2])
                return
    foe = foe_for(ctx, f, me)
    if foe is None:
        return
    if in_duel_with(ctx, me, foe) is False and ring_blocks(ctx, me, foe):
        return
    w = melee_weapon(me, None)
    bs = best_spell(ctx, me, foe)
    if bs is not None and (w is None or me.state.prefers == "spells"):
        pay(ctx, me, "action", "cast")
        cast_spell(ctx, me, foe, bs[0], bs[1], bs[2])
        return
    bow = ranged(me)
    if w is None and bow is not None and can_fire(me, bow) is None:
        pay(ctx, me, "attack", "shoot")
        fire(ctx, me, foe, bow)
        return
    for i in range(attacks_per_action(me)):
        if not upright(foe) or foe.parent.id != me.parent.id:
            break
        strike5(ctx, me, foe, w, {"knockout": bool(me.state.knockout)})
    pay(ctx, me, "action", "attack")
    ws = [it for it in held_things(me) if it.state.weapon and not it.state.ranged]
    if len(ws) >= 2 and "light" in props(ws[0]) and "light" in props(ws[1]) and upright(foe):
        strike5(ctx, me, foe, ws[1], {"offhand": True})

def fire(ctx, me, t, w):
    # a shot from a weapon that fires: the ammo is spent and lands where they stand, a loaded weapon unloads
    ammo = ammo_for(me, w)
    if w.state.loaded is not None:
        ctx.patch(w, {"loaded": False})
    far = t.parent is not None and me.parent is not None and t.parent.id != me.parent.id
    if far:
        ctx.emit("shot", target=me, reach=1, by=me.id, at=t.id, weapon=w.name)
    extra = None
    if ammo is not None:
        if ammo.state.dice:
            extra = ammo.state.dice
        ctx.transfer(ammo, t.parent, 1 if ammo.state.count is not None else None)
    return strike5(ctx, me, t, w, {"ranged": True, "extra_dice": extra})

# ---- opportunity attacks ---------------------------------------------------------------------------------------------

def opportunity(ctx, me):
    # leaving a place in a fight: each foe here with its reaction and a blade or fists swings once, unless you disengaged
    f = my_fight(ctx, me)
    if f is None or me.state.disengaged:
        return []
    out = []
    for p in ctx.children(me.parent, "creature"):
        if p.id == me.id or not upright(p) or not at_odds(ctx, p, me) or not can_react(ctx, p):
            continue
        if not upright(me):
            break
        spend_reaction(ctx, p)
        r = strike5(ctx, p, me, melee_weapon(p, None), {"opportunity": True, "knockout": bool(p.state.knockout)})
        out.append({"by": p.id, "hit": r.get("hit")})
    return out
