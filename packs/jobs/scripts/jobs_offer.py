use("jobs")
# Offer a job you give to someone here: you are its giver, or you carry it. They take it with take_job.

def mine(ctx, ref):
    # the jobs this person gives: carried, or naming them as giver anywhere
    me = ctx.actor
    low = str(ref or "").lower()
    for j in ctx.children(me):
        if j.is_a("job") and ((j.name or "").lower() == low or j.id == ref):
            return j
    for j in ctx.find(type="job", name=str(ref or ""), limit=50):
        if is_giver(j, me) and ((j.name or "").lower() == low or j.id == ref):
            return j
    return None

def check(ctx):
    ref = ctx.params.get("job")
    if not ref:
        return "offer which job? params job: one you give"
    j = mine(ctx, ref)
    if j is None:
        return "you give no job by that name"
    t = ctx.target
    if t.id == ctx.actor.id:
        return "offer it to someone else"
    if not j.state.open:
        return j.name + " is not open now"
    return True

def apply(ctx):
    j = mine(ctx, ctx.params.get("job"))
    t = ctx.target
    ctx.patch(j, {"offers": {t.id: ctx.t}})
    why = gate_wrong(ctx, j, t)
    ctx.emit("job_offered", target=t, reach=1, job=j.id, giver=ctx.actor.id, terms=j.state.terms)
    ctx.log("you offered " + t.name + " " + j.name + (" (they cannot take it yet: " + why + ")" if why else ""))
