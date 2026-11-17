use("jobs")
# Take a job posted here or offered to you: the gate, the slots and whether anyone is asking are checked first.

def check(ctx):
    ref = ctx.params.get("job")
    if not ref:
        return "take which job? params job: a name from jobs"
    j = job_named(ctx, ctx.actor, ref)
    if j is None:
        return "no job by that name is posted here or offered to you; jobs lists them"
    return take_wrong(ctx, j, ctx.actor) or True

def apply(ctx):
    me = ctx.actor
    j = job_named(ctx, me, ctx.params.get("job"))
    rec = {"since": ctx.t, "count": 0}
    days = (j.state.window or {}).get("days")
    if days:
        rec["until"] = ctx.t + float(days) * ctx.day_seconds()
        ctx.schedule(float(days) * ctx.day_seconds(), "job_due", target=j, taker=me.id)
    ch = {"holders": {me.id: rec}, "busy": True}
    if me.id in (j.state.offers or {}):
        ch["offers"] = {me.id: None}
    ctx.patch(j, ch)
    g = giver_of(ctx, j)
    ctx.emit("job_taken", target=me, reach=1, job=j.id, giver=g.id if g else None)
    ctx.log("you took " + j.name + ": " + str(j.state.terms or ""))
    return {"job": j.name, "terms": j.state.terms}
