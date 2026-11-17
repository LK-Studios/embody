use("jobs")
# Give up a job you hold: it counts as failed, and its slot is free for someone else.

def check(ctx):
    j = job_named(ctx, ctx.actor, ctx.params.get("job"))
    if j is None or ctx.actor.id not in (j.state.holders or {}):
        return "you hold no job by that name; jobs lists the ones you hold"
    return True

def apply(ctx):
    j = job_named(ctx, ctx.actor, ctx.params.get("job"))
    fail(ctx, j, ctx.actor.id, "dropped")
    ctx.log("you gave up " + j.name)
