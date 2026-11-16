use("common")
# A teacher (a body whose `teaches` names the skill) turns experience a body earned by use into a rank past what it
# reaches alone (sheet_rules' `self_taught`), up to the teacher's `up_to`. The `price`: `water` from the student's own
# water, any other key a stack of that kind the student holds (ember), handed to the teacher. `every_days` keeps a
# teacher to one lesson a student in that many world days. Only a body with a sheet trains.

def lesson(ctx):
    teaches = ctx.target.state.teaches or {}
    skill = (ctx.params or {}).get("skill")
    if not skill and len(teaches) == 1:
        skill = list(teaches.keys())[0]
    return skill, teaches.get(skill) if skill else None

def check(ctx):
    me = ctx.actor
    t = ctx.target
    teaches = t.state.teaches
    if not teaches:
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
    sheet = me.state.sheet
    rank = int((sheet.get("skills") or {}).get(skill) or 0)
    up_to = min(int(plan.get("up_to") or rules["max_rank"]), int(rules["max_rank"]))
    if rank >= up_to:
        return t.name + " has taught you all they know of " + skill + " (rank " + str(rank) + ")"
    need = int(rules["rank_cost"]) * (rank + 1)
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

def apply(ctx):
    me = ctx.actor
    t = ctx.target
    skill, plan = lesson(ctx)
    rules = sheet_rules(ctx)
    sheet = me.state.sheet
    rank = int((sheet.get("skills") or {}).get(skill) or 0)
    need = int(rules["rank_cost"]) * (rank + 1)
    xp = int((sheet.get("xp") or {}).get(skill) or 0) - need
    price = plan.get("price") or {}
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
    day = int(ctx.t // ctx.day_seconds())
    ctx.patch(me, {"sheet": {"skills": {skill: rank + 1}, "xp": {skill: xp}, "lessons": {t.id: day}}})
    ctx.emit("trained", target=me, reach=1, by=t.id, skill=skill, rank=rank + 1, xp=xp,
             next=int(rules["rank_cost"]) * (rank + 2), paid=paid)
    ctx.log(t.name + " taught you " + skill + ": rank " + str(rank + 1))
    return {"skill": skill, "rank": rank + 1, "xp": xp, "paid": paid}
