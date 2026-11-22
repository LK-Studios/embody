SKILLS = {"blade": "body", "brawl": "body", "climb": "body", "stealth": "wits", "survival": "wits", "lore": "wits", "lockpick": "wits",
          "aim": "wits", "parley": "will", "resolve": "will"}

def stat_for(skill):
    return SKILLS.get(skill, "wits")

def five_rules(ctx):
    # a world on the dnd5e pack (its settings sit on the root): no wounded penalty at half hp, exhaustion instead
    return ctx is not None and ctx.root().state.dnd5e is not None

def bonus(who, skill, ctx=None):
    # what a body adds to a d20 roll: its natural bonus (natural), less the conditions everyone can see, plus its grants
    # (with ctx: a grant for one use is spent by this roll; together at most `grant_cap` when the world sets it). A body
# with no sheet and no grants rolls stat + skill as ever.
    st = who.state
    b = natural(ctx, who, skill)
    if five_rules(ctx):
        b = b - 2 * int(st.exhaustion or 0)  # 5e: exhaustion, not wounds, weighs on every roll
    elif st.wounded:
        b = b - 2
    if st.thirsty:
        b = b - 2
    if ctx is not None and (st.grants or (st.sheet and st.aid)):
        b = b + take_grants(ctx, who, skill, who.parent)
    return b

# The sheet (packs/sheet): a body with `sheet` {attributes, skills, xp} rolls an attribute modifier plus a skill rank;
# the world's skillbook names each skill's attributes, and `sheet_rules` on the root holds every number. Every other
# body rolls body/wits/will plus a skill, as before. These are only the fallbacks when the root says nothing.
SHEET_RULES = {"earn": [[7, 0], [12, 1], [16, 2], [20, 3]], "success_x": 2, "rank_cost": 10, "max_rank": 15,
               "per_target_day": 3, "related_div": 3, "untrained": "acuity", "min_score": 1, "max_score": 20,
               "self_taught": None, "rank_costs": None, "practice_dc": None, "lesson_xp": None, "teach_skill": None,
               "attr_cap": None, "attr_cost_base": 40, "attr_cost_x": 1.6, "grant_cap": None}

def sheet_rules(ctx):
    rules = dict(SHEET_RULES)
    if ctx is not None:
        for k, v in (ctx.root().state.sheet_rules or {}).items():
            if v is not None:
                rules[k] = v
    return rules

def skillbook(ctx):
    # the world's catalogue {skill: {primary, secondary, scope, related}}, or {} where there is none
    if ctx is None:
        return {}
    for b in ctx.find(type="skillbook", limit=1):
        return b.state.skills or {}
    return {}

def attr_mod(sheet, name, rules):
    score = (sheet.get("attributes") or {}).get(name)
    score = 10 if score is None else min(int(rules["max_score"]), max(int(rules["min_score"]), int(score)))
    return (score - 10) // 2

def sheet_rank(sheet, skill, entry, rules):
    # the rank, or the best related skill's rank // related_div when that is more; related ranks never stack
    ranks = sheet.get("skills") or {}
    best = 0
    for r in entry.get("related") or []:
        best = max(best, int(ranks.get(r) or 0))
    return max(int(ranks.get(skill) or 0), best // int(rules["related_div"]))

def natural(ctx, who, skill):
    # the bonus a body has of its own: no conditions, no grants. This is what progression measures against.
    st = who.state
    sheet = st.sheet
    if not sheet:
        return int(st.get(stat_for(skill)) or 0) + int((st.skills or {}).get(skill) or 0)
    rules = sheet_rules(ctx)
    entry = skillbook(ctx).get(skill) or {}
    mod = attr_mod(sheet, entry.get("primary") or rules["untrained"], rules)
    if entry.get("secondary"):
        mod = (mod + attr_mod(sheet, entry.get("secondary"), rules)) // 2  # the two averaged, rounded down
    return mod + sheet_rank(sheet, skill, entry, rules)

def known_skill(ctx, who, skill):
    # whether the skill is one this body's rules know: the d20 ten or its own skills; with a sheet, the skillbook's
    st = who.state
    if st.sheet:
        return skill in skillbook(ctx) or skill in (st.sheet.get("skills") or {})
    return skill in SKILLS or skill in (st.skills or {})

def take_grants(ctx, who, skill, here):
    # `grants` on a body: [{source, bonus, skill, place, until, uses, condition}]. Every grant for this skill (none:
    # any) in this place (none: anywhere), not past `until` (world t), adds its bonus; from one source only the
    # largest counts. One with `uses` spends one and goes at 0; lapsed ones fall away. `condition` is the narrator's
    # words, carried, not checked. A sheet body's `aid` (a familiar's hand) is a grant for one use.
    st = who.state
    keep = []
    best = {}
    for g in st.grants or []:
        if g.get("until") is not None and float(g.get("until")) < ctx.t:
            continue
        if (not g.get("skill") or g.get("skill") == skill) and (not g.get("place") or (here is not None and g.get("place") == here.id)):
            src = str(g.get("source") or "")
            if src not in best or int(g.get("bonus") or 0) > best[src]:
                best[src] = int(g.get("bonus") or 0)
            if g.get("uses") is not None:
                if int(g.get("uses")) <= 1:
                    continue
                g = dict(g)
                g["uses"] = int(g.get("uses")) - 1
        keep.append(g)
    if st.grants is not None and keep != list(st.grants):
        ctx.patch(who, {"grants": keep})
    if st.sheet and st.aid:
        a = take_aid(ctx, who, skill, here)
        if a is not None:
            src = str(a.get("by") or "aid")
            best[src] = max(best.get(src, int(a.get("bonus") or 0)), int(a.get("bonus") or 0))
    total = sum(best.values())
    cap = sheet_rules(ctx).get("grant_cap")  # the most every grant together adds to one roll, when the world sets it
    if cap is not None and total > int(cap):
        total = int(cap)
    return total

def rank_cost(rules, rank):
    # the experience rank r to r + 1 costs: `rank_costs`[r] when the world sets a list (its last entry past its end),
    # else rank_cost x (r + 1)
    costs = rules.get("rank_costs")
    if costs:
        return int(costs[min(int(rank), len(costs) - 1)])
    return int(rules["rank_cost"]) * (int(rank) + 1)

def self_top(rules):
    # the highest rank use alone reaches: self_taught when the world sets it, else max_rank
    top = int(rules["max_rank"])
    if rules.get("self_taught") is not None:
        top = min(top, int(rules["self_taught"]))
    return top

def attr_cost(rules, score):
    # the attribute experience score s to s + 1 costs: attr_cost_base x attr_cost_x ^ (s - 10), rounded
    return int(round(float(rules["attr_cost_base"]) * float(rules["attr_cost_x"]) ** (int(score) - 10)))

def earn_for(rules, need):
    # sheet_rules' `earn` bands: the experience a roll that needed `need` earns (nothing below 1 or past the last band)
    if need < 1:
        return 0
    for band in rules["earn"]:
        if need <= int(band[0]):
            return int(band[1])
    return 0

def taught_today(ctx, sheet, key):
    # how many teaching rolls `key` (skill|target) had today, and the `taught` patch that counts one more and clears
    # earlier days (a patch merges; None deletes)
    day = int(ctx.t // ctx.day_seconds())
    taught = {}
    for k, v in (sheet.get("taught") or {}).items():
        if v[0] != day:
            taught[k] = None
    old = (sheet.get("taught") or {}).get(key)
    n = old[1] if old is not None and old[0] == day else 0
    taught[key] = [day, n + 1]
    return n, taught

def third_left(sheet, book, skill, rank, rules):
    # a capped source (practice, deeds) gives at most a third of a rank's cost toward it: sheet[book] {skill: [rank,
    # xp]} counts it, new at each rank. Returns (what is left, what it gave so far)
    got = (sheet.get(book) or {}).get(skill)
    used = int(got[1]) if got is not None and int(got[0]) == int(rank) else 0
    return max(0, rank_cost(rules, rank) // 3 - used), used

def grow(ctx, who, skill, earned, rules, new):
    # slow attribute growth: each point a skill earns is one toward its primary attribute (`attr_xp` on the sheet);
    # score s to s + 1 costs attr_cost(s), and growth stops at `attr_cap` (none: attributes never grow; max_score stays
    # for boons). Adds to the sheet patch `new`; returns [attribute, score] when one rose
    cap = rules.get("attr_cap")
    name = (skillbook(ctx).get(skill) or {}).get("primary")
    if cap is None or not name or earned <= 0:
        return None
    sheet = who.state.sheet
    score = (sheet.get("attributes") or {}).get(name)
    score = 10 if score is None else int(score)
    if score >= int(cap):
        return None
    pts = int((sheet.get("attr_xp") or {}).get(name) or 0) + earned
    was = score
    while score < int(cap) and pts >= attr_cost(rules, score):
        pts = pts - attr_cost(rules, score)
        score = score + 1
    new["attr_xp"] = {name: 0 if score >= int(cap) else pts}
    if score > was:
        new["attributes"] = {name: score}
        return [name, score]
    return None

def award(ctx, who, skill, earned, extra):
    # the one way experience lands on a sheet (use, practice, a deed, a lesson): adds it, ranks up while it can to
    # self_taught, banks past it up to the next rank (for a teacher), feeds the primary attribute, and patches the sheet
    # with `extra` too. Returns {rank, xp, next, ranked_up, teacher, grew}; the caller says it with said()
    rules = sheet_rules(ctx)
    sheet = who.state.sheet
    rank = int((sheet.get("skills") or {}).get(skill) or 0)
    xp = int((sheet.get("xp") or {}).get(skill) or 0) + earned
    was = rank
    top = self_top(rules)
    while rank < top and xp >= rank_cost(rules, rank):
        xp = xp - rank_cost(rules, rank)
        rank = rank + 1
    if rank >= int(rules["max_rank"]):
        xp = 0
    elif rank >= top:
        xp = min(xp, rank_cost(rules, rank))  # banked to the next rank, for a teacher
    new = dict(extra or {})
    grew = None
    if earned:
        new["skills"] = {skill: rank}
        new["xp"] = {skill: xp}
        grew = grow(ctx, who, skill, earned, rules, new)
    ctx.patch(who, {"sheet": new})
    full = rank >= top and rank < int(rules["max_rank"]) and xp >= rank_cost(rules, rank)
    return {"rank": rank, "xp": xp, "next": rank_cost(rules, rank), "ranked_up": rank > was, "teacher": full, "grew": grew}

def said(ctx, who, skill, earned, source, out, more):
    # the learned event on the body (reach 0: its own feed), the ledger of every award; `more` has what the source
    # adds (need, dc, success, against, why, by); `grew` names an attribute that rose with it
    ctx.emit("learned", target=who, reach=0, skill=skill, source=source, need=more.get("need"), earned=earned,
             success=more.get("success"), dc=more.get("dc"), against=more.get("against"), why=more.get("why"),
             by=more.get("by"), xp=out["xp"], rank=out["rank"], next=out["next"],
             ranked_up=out["ranked_up"], teacher=out["teacher"], grew=out["grew"])
    if out["grew"] is not None:
        ctx.emit("grew", target=who, reach=0, attribute=out["grew"][0], score=out["grew"][1], skill=skill)

def learn(ctx, who, skill, dc, success, against=None):
    # use-based progression for a body with a sheet: only a difficulty the world set teaches (a find, a lock, a hazard,
    # a world verb's dc, an opposed roll), never a check whose dc the caller chose. The roll it needed is dc less its
    # natural bonus (no grants, no conditions); sheet_rules' `earn` bands turn that into experience, a success times
    # `success_x`; rank r to r + 1 costs rank_cost(rules, r), up to max_rank. At most `per_target_day` teaching rolls
    # a skill, a target, a world day. Past `self_taught` (when the root sets it) use banks experience up to the next
    # rank and a teacher's train turns it into one. Every award is a `learned` event on the body. Returns what it
    # earned. Only the world's rules teach: under a guest's script, a frame or a programmed verb it teaches nothing.
    st = who.state
    sheet = st.sheet
    if not sheet or not skill or st.dead or not ctx.may_write_sheet():
        return 0
    rules = sheet_rules(ctx)
    need = int(dc) - natural(ctx, who, skill)
    earned = earn_for(rules, need)
    if success:
        earned = earned * int(rules["success_x"])
    n, taught = taught_today(ctx, sheet, skill + "|" + (against.id if against is not None else ""))
    if n >= int(rules["per_target_day"]):
        return 0
    out = award(ctx, who, skill, earned, {"taught": taught})
    if earned:
        said(ctx, who, skill, earned, "use", out, {"need": need, "dc": dc, "success": bool(success),
                                                   "against": against.id if against is not None else None})
    return earned

def deed(ctx, who, skill, amount, why):
    # a story deed's experience, for a world's own scripts (the world decides which deeds count and how much): at most
    # a third of the rank's cost comes from deeds (`deeds` on the sheet, new each rank), apart from practice's third.
    # A learned event with source "deed" and the why. Only the world's rules award it. Returns what it gave.
    st = who.state
    sheet = st.sheet
    if not sheet or not skill or st.dead or not ctx.may_write_sheet() or int(amount) <= 0:
        return 0
    rules = sheet_rules(ctx)
    rank = int((sheet.get("skills") or {}).get(skill) or 0)
    if rank >= int(rules["max_rank"]):
        return 0
    left, used = third_left(sheet, "deeds", skill, rank, rules)
    earned = min(int(amount), left)
    if earned <= 0:
        return 0
    out = award(ctx, who, skill, earned, {"deeds": {skill: [rank, used + earned]}})
    said(ctx, who, skill, earned, "deed", out, {"why": str(why)})
    return earned

def weapon_skill(who, weapon, old):
    # a weapon names its skill (`skill`: "short blades"); a body with no sheet, or a weapon that names none, rolls the old one
    if weapon is not None and who.state.sheet and weapon.state.skill:
        return weapon.state.skill
    return old

def take_aid(ctx, who, skill, here):
    # a hand from someone (a familiar's `point`): `aid` on the body is a list of {bonus, skill, place, by, why, until}.
    # The first one for this skill (none: any skill) in this place (none: anywhere), not past `until` (world t), is
    # used up by this check and returned; lapsed ones fall away. None when nothing helps.
    aids = who.state.aid or []
    if not aids:
        return None
    keep = []
    used = None
    for a in aids:
        if a.get("until") is not None and float(a.get("until")) < ctx.t:
            continue
        fits = (not a.get("skill") or a.get("skill") == skill) and (not a.get("place") or (here is not None and a.get("place") == here.id))
        if used is None and fits:
            used = a
            continue
        keep.append(a)
    if len(keep) != len(aids):
        ctx.patch(who, {"aid": keep})
    return used

def held(who, flag):
    # the first thing held whose state has the flag set
    for it in who.children():
        if it.state.get(flag):
            return it
    return None

def endless(thing):
    # a source with no level never runs dry: a well, a spring, a place that is a source; drawing from it costs nobody's count
    return thing is not None and bool(thing.state.water_source) and thing.state.left is None

def kept_for(src, who):
    # whether a body's own idle care may drink from this source: `keep_for` names whose water it is (a faction,
    # an id, or a list of them); none means anyone's. A seat that chooses to drink from another's store still can.
    keep = src.state.keep_for
    if who is None or keep is None:
        return True
    names = keep if isinstance(keep, list) else [keep]
    return who.id in names or (who.state.faction is not None and who.state.faction in names)

def water_here(ctx, place, who=None):
    # the place itself if it is a source, else the thing here that is one with the most left (an endless one
    # first). With `who`, only the water kept for them (kept_for).
    if place is None:
        return None
    if place.state.water_source and kept_for(place, who):
        return place
    best = None
    for p in ctx.children(place, "thing"):
        if not p.state.water_source or not kept_for(p, who):
            continue
        if p.state.left is None:
            return p
        if int(p.state.left) > 0 and (best is None or int(p.state.left) > int(best.state.left)):
            best = p
    return best

def known_way(who, place):
    # a hidden place is on a body's map only if it is its own side's
    return not (place.state.hidden and place.state.known_to != who.state.faction)

def way_out(place):
    # a place you may step out of into the place that holds it, with no way drawn between them: one that says
    # `way_out` (a tent, a cart), or a vehicle (the vehicles pack: its way out is alight)
    if place.state.way_out is not None:
        return bool(place.state.way_out)
    return place.is_a("vehicle")

def ways_from(ctx, pid):
    # the places one step from a place: its ways, and the place that holds it when it may be stepped out of
    out = [e["target"] for e in ctx.edges(pid, "connects_to", "out")]
    p = ctx.get(pid)
    if p is not None and p.parent is not None and way_out(p):
        out.append(p.parent.id)
    return out

def first_step(ctx, who, here, goal, limit):
    # breadth-first over the ways (and out of a vehicle or anything else that may be stepped out of): the first step
    # on the shortest way this body knows to `goal` (a place id), or, with goal None, to the nearest place with water
    # in it. None when there is none within `limit` steps. It never steps into or through a place where someone of a
    # side that has outlawed this body stands (watched): the walk goes around them, or waits.
    foes = outlawed_by(ctx, who)
    seen = {here.id: True}
    frontier = [[here.id, None]]
    for depth in range(limit):
        nxt = []
        for item in frontier:
            for tid in ways_from(ctx, item[0]):
                if tid in seen:
                    continue
                seen[tid] = True
                t = ctx.get(tid)
                if t is None or watched(ctx, t, foes):
                    continue
                first = item[1] if item[1] is not None else tid
                if tid == goal:
                    return ctx.get(first)
                if not known_way(who, t):
                    continue
                if goal is None and water_here(ctx, t, who) is not None:
                    return ctx.get(first)
                nxt.append([tid, first])
        frontier = nxt
    return None

def outlawed_by(ctx, who):
    # the names of the sides that have outlawed this body, once time has forgiven what it will
    out = []
    for f in ctx.find(type="faction", limit=20):
        if (f.state.hostile or {}).get(who.id) and outlaw_of(ctx, f, who):
            out.append(f.name)
    return out

def watched(ctx, place, foes):
    # someone of one of these sides stands here, on their feet: a place a body's own walks keep clear of
    if not foes:
        return False
    for p in ctx.children(place, "creature"):
        if p.state.faction in foes and not p.state.down and not p.state.dead:
            return True
    return False

def water_near(ctx, who, here):
    # the first step toward the nearest water this body knows the way to (six steps at most)
    return first_step(ctx, who, here, None, 6)

def revive(ctx, who, water):
    # a body thirst put down gets up when it has drunk; a blade's work stays done until someone sees to it
    st = who.state
    if st.down and st.downed_by == "thirst" and water > 3:
        ctx.patch(who, {"down": False, "downed_by": None, "hp": max(1, int(st.hp or 0)), "dry_since": None, "fading": None})
        ctx.emit("rose", target=who, reach=1, by="water")

# how many world days a body left down and dry lasts, by its body: the days for a body of at least that much. A world
# tunes it with `thirst_death_days` on its root (the same shape), or false for a thirst that never kills.
THIRST_DEATH_DAYS = {"0": 1, "3": 2, "4": 3}

def thirst_days(ctx, who):
    table = ctx.root().state.thirst_death_days
    if table is False:
        return None
    table = table or THIRST_DEATH_DAYS
    body = int(who.state.body or 0)
    days = None
    best = -1
    for k in table:
        if int(k) <= body and int(k) > best:
            best = int(k)
            days = table[k]
    return days

def fade(ctx, who):
    # a body thirst put down that stays dry: `fading` each world day it lasts, so whoever finds it sees the time
    # running out, and `died` (why thirst) when its days are spent. The count starts when it went down.
    st = who.state
    days = thirst_days(ctx, who)
    if days is None:
        return
    if st.dry_since is None:
        ctx.patch(who, {"dry_since": ctx.t})  # down before deaths by thirst existed: its days start now
        return
    gone = (ctx.t - float(st.dry_since)) / ctx.day_seconds()
    if gone >= float(days):
        ctx.patch(who, {"dead": True, "hp": 0, "dry_since": None, "fading": None})
        ctx.emit("died", target=who, reach=-1, why="thirst", days=days)
        return
    n = int(gone)
    if n >= 1 and n > int(st.fading or 0):
        ctx.patch(who, {"fading": n})
        ctx.emit("fading", target=who, reach=1, why="thirst", day=n, of=days)

def settle(ctx, who, cause):
    # derive the conditions from hp and say what changed
    st = who.state
    v = int(st.hp or 0)
    mx = int(st.max_hp or 6)
    if v <= 0 and not st.down:
        ctx.patch(who, {"down": True, "wounded": True, "hp": 0, "braced": False})
        ctx.emit("downed", target=who, reach=1, by=cause)
    elif v <= mx // 2 and not st.wounded and not five_rules(ctx):
        ctx.patch(who, {"wounded": True})
        ctx.emit("wounded", target=who, reach=1, by=cause)

# heavy work makes a body sweat: a point of water for a blow in a fight, a harvest, a dig, dressing stone, forcing a
# lock, or a walk to or from open ground under more than half its carry. A world tunes it with `sweat` on its root: a
# table of costs by key (a verb, or "fight" and "heavy_walk") over these, or false for none.
SWEAT = {"fight": 1, "harvest": 1, "dig": 1, "dress": 1, "break": 1, "heavy_walk": 1}

def sweat_cost(ctx, key):
    table = ctx.root().state.sweat
    if table is False:
        return 0
    if table and table.get(key) is not None:
        return table.get(key)
    return SWEAT.get(key, 0)

def sweat(ctx, who, key):
    n = sweat_cost(ctx, key)
    st = who.state
    if not n or st.dead or st.water is None:
        return 0
    water = max(0, int(st.water) - int(n))
    changes = {"water": water}
    if water <= 3 and not st.thirsty:
        changes["thirsty"] = True
    ctx.patch(who, changes)
    ctx.emit("sweated", target=who, reach=0, by=key, cost=n, water=water)
    if changes.get("thirsty"):
        ctx.emit("thirsty", target=who, reach=0, water=water)
    return n

def strike(ctx, me, t, slow):
    # one blow: the opposed roll, the ward, the damage, the conditions. Used by attack and by fighters' ticks.
    sweat(ctx, me, "fight")
    weapon = melee(me)
    wname = weapon.name if weapon else "bare hands"
    ward = held(t, "ward")
    if not t.state.yielded:
        ctx.patch(t, {"attacked_by": me.id, "attacked_at": ctx.t})  # the grudge, and when it was last fed
    if t.state.yielded == me.id:
        ctx.emit("dishonor", target=me, reach=-1, against=t.id)
    cx = (weapon.state.cooldown_x if weapon else None) or 1  # a maul's 2: the engine holds the striker off longer
    if ward and ward.state.on and not slow:
        ctx.emit("warded", target=t, reach=1, by=me.id, weapon=wname)
        ctx.log("the ward hardens against the fast blow")
        return {"hit": False, "warded": True, "cooldown_x": cx}
    # a sleeper is struck with advantage (the better of two rolls) and defends with bare hands, unbraced
    asleep = bool(t.state.asleep)
    a_roll = ctx.rand.roll("1d20")
    rolls = [a_roll]
    if asleep:
        rolls.append(ctx.rand.roll("1d20"))
        a_roll = max(rolls)
    a_skill = weapon_skill(me, weapon, "blade") if weapon else "brawl"
    a_mod = bonus(me, a_skill, ctx)
    if weapon:
        a_mod = a_mod + int(weapon.state.bonus or 0)
    if slow:
        a_mod = a_mod - 2
    d_roll = ctx.rand.roll("1d20")
    d_skill = weapon_skill(t, melee(t), "blade") if melee(t) and not asleep else "brawl"
    d_mod = bonus(t, d_skill, ctx)
    if t.state.braced and not asleep:
        d_mod = d_mod + 3
    attack = a_roll + a_mod
    defence = d_roll + d_mod
    hit = attack > defence
    learn(ctx, me, a_skill, defence + 1, hit, t)  # an opposed roll teaches both sides
    if not asleep:
        learn(ctx, t, d_skill, attack, not hit, me)
    dmg = 0
    if hit:
        dmg = int(weapon.state.damage or 1) if weapon else 1
        hp = int(t.state.hp or 0) - dmg
        ctx.patch(t, {"hp": hp, "braced": False})
        ctx.emit("hit", target=t, reach=1, by=me.id, dmg=dmg, weapon=wname, attack=attack, defence=defence, hp=hp,
                 rolls=rolls, asleep=asleep)
        scar(ctx, t, dmg, wname)
        settle(ctx, t, me.id)
    else:
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon=wname, attack=attack, defence=defence, rolls=rolls,
                 asleep=asleep)
    if me.state.braced:
        ctx.patch(me, {"braced": False})
    ctx.log(("hit for " + str(dmg) if hit else "miss") + " (" + str(attack) + " vs " + str(defence) + ")")
    return {"hit": hit, "dmg": dmg, "attack": attack, "defence": defence, "cooldown_x": cx}

SCAR_REGIONS = ["head", "face", "neck", "torso", "back", "arms", "hands", "legs", "feet"]

def scar(ctx, t, dmg, how):
    # with the root's `looks_rules` {scar_damage} set (none by default), a hit that deals at least that much leaves a
    # permanent near mark, "a fresh scar", on a region of the body the world's dice pick (src/embody/looks.py)
    need = (ctx.root().state.looks_rules or {}).get("scar_damage")
    if need is None or dmg < int(need) or not t.is_a("creature") or not ctx.may_write_sheet():
        return None
    lk = t.state.looks or {}
    if len(lk.get("marks") or {}) >= 40:
        return None
    where = ctx.rand.choice(lk.get("regions") or SCAR_REGIONS)
    return ctx.mark(t, where, "a fresh scar from " + how, "permanent", "near", None)

def melee(who):
    # the first weapon held that is not one that fires: what a blow is struck with
    for it in who.children():
        if it.state.weapon and not it.state.ranged:
            return it
    return None

def ranged(who):
    # the first weapon held that fires (`ranged` on its state); `ammo` names the kind it takes
    for it in who.children():
        if it.state.weapon and it.state.ranged:
            return it
    return None

def ammo_for(who, weapon):
    # what the weapon fires from the shooter's hands: a held thing whose `ammo` or `kind` is the weapon's `ammo`
    # (a stack of arrows, a pouch of glass for a sling). A weapon with no `ammo` needs none.
    kind = weapon.state.ammo
    for it in who.children():
        if kind and it.id != weapon.id and (it.state.ammo == kind or it.state.kind == kind):
            return it
    return None

def can_fire(who, weapon):
    # why it will not fire now, or None: a weapon that must be loaded (`loaded` false) and one out of ammo
    if weapon.state.loaded is False:
        return weapon.name + " is not loaded"
    if weapon.state.ammo and ammo_for(who, weapon) is None:
        return "you have no " + str(weapon.state.ammo) + " left"
    return None

def in_sight(ctx, me, t):
    # someone here, or one way over that the eye can follow: a way you know with no shut door on it
    here = me.parent
    there = t.parent
    if here is None or there is None:
        return False
    if there.id == here.id:
        return True
    if t.state.hidden:
        return False
    for e in ctx.edges(here, "connects_to", "out"):
        if e["target"] == there.id:
            via = ctx.get(e["data"].get("via")) if e["data"].get("via") else None
            if via is not None and not via.state.open:
                return False
            return ctx.knows_way(me, there)
    return False

def cover(place):
    # `cover` on a place: true is +2 to the defence of whoever stands in it, a number is that much
    c = place.state.cover if place is not None else None
    if c is True:
        return 2
    if c:
        return int(c)
    return 0

def ring_blocks(ctx, a, t):
    # the ring holds against shots too: one in a duel shoots only the other, nobody shoots into a duel
    for d in ctx.relations(a, "duel"):
        if t.id not in d["participants"]:
            return "you are in a duel: your aim is for your opponent"
    for d in ctx.relations(t, "duel"):
        if a.id not in d["participants"]:
            return "the ring holds: " + t.name + " is in a duel"
    return None

def shot(ctx, me, t, weapon):
    # one shot from a weapon that fires, at someone in sight (in_sight). The hook a world's own fire verbs call (a
    # crossbow that is loaded, a sling): d20 + wits + aim + the weapon's bonus, -2 one way over, against d20 + wits
    # + the cover where they stand. A ward on stops it: a shot is fast. The ammo is spent and lands where they
    # stand, hit or miss, a pile anyone there can take; a loaded weapon is unloaded.
    ammo = ammo_for(me, weapon)
    if weapon.state.loaded is not None:
        ctx.patch(weapon, {"loaded": False})
    provoke(ctx, me, t)
    extra = int(ammo.state.damage or 0) if ammo is not None else 0
    if ammo is not None:
        ctx.transfer(ammo, t.parent, 1 if ammo.state.count is not None else None)
    r = loose(ctx, me, t, weapon.name, weapon_skill(me, weapon, "aim"), int(weapon.state.bonus or 0),
              int(weapon.state.damage or 1) + extra, None)
    r["cooldown_x"] = weapon.state.cooldown_x or 1
    return r

def provoke(ctx, me, t):
    # what any blow or shot does before it lands: it feeds the target's grudge, and striking one who yielded is dishonor
    if not t.state.yielded:
        ctx.patch(t, {"attacked_by": me.id, "attacked_at": ctx.t})  # the grudge, and when it was last fed
    if t.state.yielded == me.id:
        ctx.emit("dishonor", target=me, reach=-1, against=t.id)

def loose(ctx, me, t, label, skill, mod, dmg, die):
    # the flight of a shot, by whatever looses it (a bow, a gift: packs/gifts): d20 + the skill + mod, -2 one way over,
    # against d20 + dodge + the cover where they stand. A ward on stops it. A hit does `die` rolled (dice like "1d4")
    # or else `dmg`, and puts its conditions on them. `label` names it in the events.
    far = t.parent.id != me.parent.id
    wname = label
    if far:
        ctx.emit("shot", target=me, reach=1, by=me.id, at=t.id, weapon=wname)  # the shooter's own place sees it fly
    ward = held(t, "ward")
    if ward and ward.state.on:
        ctx.emit("warded", target=t, reach=1, by=me.id, weapon=wname, ranged=True)
        ctx.log("the ward stops the shot")
        return {"hit": False, "warded": True}
    asleep = bool(t.state.asleep)
    a_roll = ctx.rand.roll("1d20")
    rolls = [a_roll]
    if asleep:
        rolls.append(ctx.rand.roll("1d20"))
        a_roll = max(rolls)
    a_skill = skill
    a_mod = bonus(me, a_skill, ctx) + int(mod or 0) - (2 if far else 0)
    d_roll = ctx.rand.roll("1d20")
    d_mod = cover(t.parent) + (0 if asleep else bonus(t, "dodge", ctx))  # wits, less the conditions
    attack = a_roll + a_mod
    defence = d_roll + d_mod
    hit = attack > defence
    learn(ctx, me, a_skill, defence + 1, hit, t)
    if not asleep:
        learn(ctx, t, "dodge", attack, not hit, me)
    if hit:
        dmg = ctx.rand.roll(die) if die else int(dmg)
        hp = int(t.state.hp or 0) - dmg
        ctx.patch(t, {"hp": hp, "braced": False})
        ctx.emit("hit", target=t, reach=1, by=me.id, dmg=dmg, weapon=wname, attack=attack, defence=defence, hp=hp,
                 rolls=rolls, asleep=asleep, ranged=True)
        scar(ctx, t, dmg, wname)
        settle(ctx, t, me.id)
    else:
        dmg = 0
        ctx.emit("missed", target=t, reach=1, by=me.id, weapon=wname, attack=attack, defence=defence, rolls=rolls,
                 asleep=asleep, ranged=True)
    ctx.log(("hit for " + str(dmg) if hit else "miss") + " (" + str(attack) + " vs " + str(defence) + ")")
    return {"hit": hit, "dmg": dmg, "attack": attack, "defence": defence, "far": far}

def grudge_for(ctx):
    # how long a fighter keeps a grudge with no blow from its foe: root `grudge_for`, world seconds (default an hour)
    g = ctx.root().state.grudge_for
    return 3600 if g is None else float(g)

def faction_of(ctx, who):
    name = who.state.faction
    if not name:
        return None
    for f in ctx.find(type="faction", limit=20):
        if f.name == name:
            return f
    return None

def seen_standing(ctx, who, faction):
    # what the person can read: their out-edge to the faction
    for e in ctx.edges(who, "standing", "out"):
        if e["target"] == faction.id:
            return int(e["data"].get("value") or 0)
    return 0

def standing(ctx, who, faction):
    # where the person stands: what they can read, plus what the faction keeps to itself (`unseen`)
    return seen_standing(ctx, who, faction) + int((faction.state.unseen or {}).get(who.id) or 0)

def keep_secret(ctx, thing, changes):
    # patch keys on a thing and list them in its `secret`, so no body reads them on its card
    secret = list(thing.state.secret or [])
    for k in changes:
        if k not in secret:
            secret.append(k)
    changes = dict(changes)
    changes["secret"] = secret
    ctx.patch(thing, changes)

def shift_standing(ctx, who, faction, delta, why, quiet=False, blow=False):
    # an out-edge from the person, so they can read where they stand; hostility is kept on the faction.
    # quiet: the deed was done to someone who keeps their faction secret. The faction still counts it, in its own
    # secret `unseen`, and the person's edge and feed name no side they cannot know.
    # blow: the loss came from a blow, which time forgives (forgive). What time has forgiven counts first.
    forgive(ctx, who, faction)
    value = move_standing(ctx, who, faction, delta, why, quiet)
    if blow and delta < 0:
        bruise(ctx, who, faction, -delta, quiet)
    return value

def bruise(ctx, who, faction, n, quiet):
    # standing lost to blows, kept secret on the faction (`bruised`: how much is left to forgive, and since when).
    # A new blow starts the day again. The body keeps the factions in its secret `bruised_with`, so its own rest
    # (mend) can see the day come.
    bruised = dict(faction.state.bruised or {})
    rec = bruised.get(who.id) or {}
    bruised[who.id] = {"n": int(rec.get("n") or 0) + n, "at": ctx.t, "quiet": bool(quiet)}
    keep_secret(ctx, faction, {"bruised": bruised})
    if faction.id not in (who.state.bruised_with or []):
        keep_secret(ctx, who, {"bruised_with": list(who.state.bruised_with or []) + [faction.id]})

def forgive(ctx, who, faction):
    # standing lost to blows climbs back a point a world day after the last blow, up to -3, just above outlaw: a
    # fight nobody keeps up burns out, and one a mind keeps striking stays alive. Returns the points given back.
    bruised = dict(faction.state.bruised or {})
    rec = bruised.get(who.id)
    if not rec:
        return 0
    day = ctx.day_seconds()
    days = int((ctx.t - float(rec["at"])) // day)
    if days <= 0:
        return 0
    room = -3 - standing(ctx, who, faction)
    k = max(0, min(days, int(rec["n"]), room))
    if k >= int(rec["n"]) or k >= room:
        bruised[who.id] = None  # all forgiven, or as far up as time goes
    else:
        bruised[who.id] = {"n": int(rec["n"]) - k, "at": float(rec["at"]) + k * day, "quiet": rec.get("quiet")}
    keep_secret(ctx, faction, {"bruised": bruised})
    if k > 0:
        move_standing(ctx, who, faction, k, "blows forgiven", rec.get("quiet"))
    return k

def forgive_all(ctx, who):
    # every faction this body has a bruise with: what the days since have forgiven (mend calls it)
    left = []
    for fid in who.state.bruised_with or []:
        f = ctx.get(fid)
        if f is None:
            continue
        forgive(ctx, who, f)
        if (f.state.bruised or {}).get(who.id):
            left.append(fid)
    if left != list(who.state.bruised_with or []):
        ctx.patch(who, {"bruised_with": left or None})

def outlaw_of(ctx, faction, who):
    # still outlawed by the faction, once time has forgiven what it will
    if not (faction.state.hostile or {}).get(who.id):
        return False
    forgive(ctx, who, faction)
    return bool((faction.state.hostile or {}).get(who.id))

def move_standing(ctx, who, faction, delta, why, quiet=False):
    seen = seen_standing(ctx, who, faction)
    unseen = dict(faction.state.unseen or {})
    if quiet:
        unseen[who.id] = int(unseen.get(who.id) or 0) + delta
        keep_secret(ctx, faction, {"unseen": unseen})
    else:
        seen = seen + delta
        ctx.unlink(who, faction, "standing")
        ctx.link(who, faction, "standing", {"value": seen, "public": True})
        ctx.emit("standing", target=who, reach=0, faction=faction.name, value=seen, delta=delta, why=why)
    value = seen + int(unseen.get(who.id) or 0)
    hostile = dict(faction.state.hostile or {})
    if value <= -4 and not hostile.get(who.id):
        hostile[who.id] = True
        ctx.patch(faction, {"hostile": hostile})
        ctx.emit("outlawed", target=who, reach=1, faction=faction.name)
    elif value > -4 and hostile.get(who.id):
        hostile[who.id] = None
        ctx.patch(faction, {"hostile": hostile})
    return value
