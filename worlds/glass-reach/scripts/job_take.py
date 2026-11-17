# Take a job from its giver, who has to be here: it is a promise between the two of you, on the record.
use("reach_job")

def check(ctx):
    if ctx.target.parent is None or ctx.actor.parent is None or ctx.target.parent.id != ctx.actor.parent.id:
        return "it is not here"
    if not ctx.target.state.job:
        return "there is no work on this"
    why = why_not(ctx, ctx.target, ctx.actor)
    return why if why else True

def apply(ctx):
    j = job_of(ctx.target)
    giver = ctx.get(j.get("giver"))
    j["takers"] = list(j.get("takers") or []) + [{"who": ctx.actor.id, "t": ctx.t}]
    ctx.patch(ctx.target, {"job": j})
    ctx.emit("job_taken", target=ctx.actor.parent, reach=1, by=ctx.actor.id, giver=giver.id, job=j.get("id"),
             text=line(j, "taken", ctx.actor, giver))
    ctx.log(line(j, "terms", ctx.actor, giver))
    return {"job": j.get("id"), "terms": line(j, "terms", ctx.actor, giver)}
