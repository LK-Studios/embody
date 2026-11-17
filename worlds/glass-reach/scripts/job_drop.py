# Give a job back: the promise is off, and the giver hears it. Anyone may take it again while it is open.
use("reach_job")

def check(ctx):
    j = job_of(ctx.target)
    if ctx.actor.id not in taker_ids(j):
        return "you have not taken this work"
    return True

def apply(ctx):
    j = job_of(ctx.target)
    j["takers"] = [d for d in (j.get("takers") or []) if d.get("who") != ctx.actor.id]
    ctx.patch(ctx.target, {"job": j})
    ctx.emit("job_dropped", target=ctx.actor, reach=0, by=ctx.actor.id, giver=j.get("giver"), job=j.get("id"))
    giver = ctx.get(j.get("giver")) if j.get("giver") else None
    if giver is not None:
        ctx.emit("job_dropped", target=giver, reach=0, by=ctx.actor.id, giver=giver.id, job=j.get("id"))
    ctx.log("you give the work back")
