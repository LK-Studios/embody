use("common")
# Practice: an hour on a skill alone, rolled against the world's dc for the rank (sheet_rules `practice_dc`, a list by
# rank; none: 10 + rank). It earns by the same bands as use, at least 1 for the time spent, times success_x on a
# success, and at most a third of the rank's cost comes from practice (`practiced` on the sheet, new each rank): the
# rest comes from use out in the world, deeds and teachers. Each practice is that skill's teaching roll on "practice"
# for the day. Grants are not spent on it. Only a body with a sheet practices.

def practice_dc(rules, rank):
    dcs = rules.get("practice_dc")
    if dcs:
        return int(dcs[min(rank, len(dcs) - 1)])
    return 10 + rank

def which(ctx):
    return str((ctx.params or {}).get("skill") or "")

def check(ctx):
    me = ctx.actor
    sheet = me.state.sheet
    if not sheet:
        return "only a body with a sheet practices: its skills grow by rank"
    skill = which(ctx)
    if not skill:
        return "practice which skill? params {\"skill\": \"...\"} (guide('skills') lists them)"
    if skill not in skillbook(ctx):
        return "no skill '" + skill + "' in this world's skillbook: guide('skills') lists them"
    if me.state.down or me.state.dead or me.state.asleep:
        return "you are in no state to practice"
    rules = sheet_rules(ctx)
    rank = int((sheet.get("skills") or {}).get(skill) or 0)
    if rank >= int(rules["max_rank"]):
        return "you have mastered " + skill + ": rank " + str(rank) + " is the most there is"
    left, used = third_left(sheet, "practiced", skill, rank, rules)
    if left <= 0:
        return ("practice has given all it will toward rank " + str(rank + 1) + " in " + skill + " (a third of its "
                + str(rank_cost(rules, rank)) + "): the rest comes from use out in the world, deeds and teachers")
    n, taught = taught_today(ctx, sheet, skill + "|practice")
    if n >= int(rules["per_target_day"]):
        return "you have practiced " + skill + " all it will teach today: again in a later day"
    return True

def apply(ctx):
    me = ctx.actor
    skill = which(ctx)
    rules = sheet_rules(ctx)
    sheet = me.state.sheet
    rank = int((sheet.get("skills") or {}).get(skill) or 0)
    dc = practice_dc(rules, rank)
    roll = ctx.rand.roll("1d20")
    mod = bonus(me, skill)  # conditions count; no ctx, so no grant is spent
    ok = roll + mod >= dc
    need = dc - natural(ctx, me, skill)
    earned = max(1, earn_for(rules, need))  # the time spent always teaches a little
    if ok:
        earned = earned * int(rules["success_x"])
    left, used = third_left(sheet, "practiced", skill, rank, rules)
    earned = min(earned, left)
    n, taught = taught_today(ctx, sheet, skill + "|practice")
    out = award(ctx, me, skill, earned, {"taught": taught, "practiced": {skill: [rank, used + earned]}})
    said(ctx, me, skill, earned, "practice", out, {"need": need, "dc": dc, "success": ok})
    ctx.log("practice " + skill + ": d20 " + str(roll) + " + " + str(mod) + " = " + str(roll + mod) + " vs " + str(dc)
            + (" pass" if ok else " fail") + ", +" + str(earned) + " experience (" + str(out["xp"]) + "/" + str(out["next"]) + ")")
    return {"skill": skill, "roll": roll, "mod": mod, "total": roll + mod, "dc": dc, "success": ok, "earned": earned,
            "rank": out["rank"], "xp": out["xp"], "next": out["next"], "practice_left": left - earned}
