use("common")
# A teacher (a body whose `teaches` names the skill) teaches from rank 1. Below the rank a body reaches alone
# (sheet_rules' `self_taught`) a lesson gives experience (`lesson_xp`; none: a third of the rank's cost); at or past it
# the teacher turns experience the body earned by use into the next rank. A teacher teaches only below its own rank in
# the skill (a sheet's rank, or a flat skill), up to its `up_to`, and with `teach_skill` set (the Reach: teaching) only
# with rank 1 or more in that too. The `price`: `water` from the student's own water, any other key a stack of that kind
# the student holds (ember), handed to the teacher. `every_days` keeps a teacher to one lesson a student in that many
# world days. Only a body with a sheet trains.

def lesson(ctx):
    teaches = ctx.target.state.teaches
    if not isinstance(teaches, dict):
        teaches = {}
    skill = (ctx.params or {}).get("skill")
    if not skill and len(teaches) == 1:
        skill = list(teaches.keys())[0]
    return skill, teaches.get(skill) if skill else None

def rank_of(who, skill):
    # a body's own rank in a skill: its sheet's, or its flat skill without one
    if who.state.sheet:
        return int((who.state.sheet.get("skills") or {}).get(skill) or 0)
    return int((who.state.skills or {}).get(skill) or 0)

def check(ctx):
    me = ctx.actor
    t = ctx.target
    teaches = t.state.teaches
    if not teaches or not isinstance(teaches, dict):  # a world's own way of teaching (a pilot's list) is not train's
        return t.name + " teaches nothing"
    if t.id == me.id:
        return "a teacher teaches someone else"
    if not me.state.sheet:
        return "only a body with a sheet trains: its skills grow by rank"
    if t.state.down or t.state.dead or t.state.asleep:
        return t.name + " is in no state to teach"
    skill, plan = lesson(ctx)
    if plan is None:
        return t.name + " teaches " + ", ".join(sorted(teaches.keys())) + ": params {\"skill\": \"...\"}"
    rules = sheet_rules(ctx)
    how = rules.get("teach_skill")
    if how and rank_of(t, how) < 1:
        return t.name + " knows " + skill + " but not how to teach it (" + how + " 0)"
    sheet = me.state.sheet
    rank = int((sheet.get("skills") or {}).get(skill) or 0)
    up_to = min(int(plan.get("up_to") or rules["max_rank"]), int(rules["max_rank"]), rank_of(t, skill))
    if rank >= up_to:
        return t.name + " has taught you all they know of " + skill + " (rank " + str(rank) + ")"
    if rank >= self_top(rules):
        need = rank_cost(rules, rank)
        xp = int((sheet.get("xp") or {}).get(skill) or 0)
        if xp < need:
            return "you have " + str(xp) + " of the " + str(need) + " experience rank " + str(rank + 1) + " in " + skill + " needs: earn it by use first"
    last = (sheet.get("lessons") or {}).get(t.id)
    every = plan.get("every_days")
    if every and last is not None and int(ctx.t // ctx.day_seconds()) - int(last) < int(every):
        return t.name + " will teach you again in a later day"
    price = plan.get("price") or {}
    for k, n in price.items():
        if k == "water":
            if int(me.state.water or 0) < int(n):
                return "the lesson costs " + str(n) + " water and you have " + str(int(me.state.water or 0))
        else:
            have = 0
            for it in me.children():
                if it.state.kind == k:
                    have = have + int(it.state.count or 1)
            if have < int(n):
                return "the lesson costs " + str(n) + " " + k + " and you hold " + str(have)
    return True

def pay(ctx, me, t, price):
    paid = {}
    for k, n in price.items():
        if k == "water":
            ctx.patch(me, {"water": int(me.state.water or 0) - int(n)})
        else:
            left = int(n)
            for it in me.children():
                if left > 0 and it.state.kind == k:
                    take = min(left, int(it.state.count or 1))
                    ctx.transfer(it, t, take)
                    left = left - take
        paid[k] = int(n)
    return paid

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    skill, plan = lesson(ctx)
    rules = sheet_rules(ctx)
    sheet = me.state.sheet
    rank = int((sheet.get("skills") or {}).get(skill) or 0)
    paid = pay(ctx, me, t, plan.get("price") or {})
    day = int(ctx.t // ctx.day_seconds())
    if rank < self_top(rules):
        # below what a body reaches alone: the lesson is experience, and it may carry a rank with it
        gain = rules.get("lesson_xp")
        gain = int(gain) if gain is not None else max(1, rank_cost(rules, rank) // 3)
        out = award(ctx, me, skill, gain, {"lessons": {t.id: day}})
        said(ctx, me, skill, gain, "lesson", out, {"by": t.id})
        ctx.emit("trained", target=me, reach=1, by=t.id, skill=skill, rank=out["rank"], xp=out["xp"], next=out["next"],
                 earned=gain, paid=paid)
        ctx.log(t.name + " taught you " + skill + ": +" + str(gain) + " experience (" + str(out["xp"]) + "/" + str(out["next"]) + ")"
                + (", rank " + str(out["rank"]) if out["ranked_up"] else ""))
        return {"skill": skill, "rank": out["rank"], "xp": out["xp"], "earned": gain, "paid": paid}
    xp = int((sheet.get("xp") or {}).get(skill) or 0) - rank_cost(rules, rank)
    ctx.patch(me, {"sheet": {"skills": {skill: rank + 1}, "xp": {skill: xp}, "lessons": {t.id: day}}})
    ctx.emit("trained", target=me, reach=1, by=t.id, skill=skill, rank=rank + 1, xp=xp, next=rank_cost(rules, rank + 1),
             paid=paid)
    ctx.log(t.name + " taught you " + skill + ": rank " + str(rank + 1))
    return {"skill": skill, "rank": rank + 1, "xp": xp, "paid": paid}
