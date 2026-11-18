# The Reach's side of its jobs (the jobs pack keeps, checks and pays them, packs/jobs/pack.py): trouble about a job's
# beasts opens it again, and a job's sign shows it, on its peg while the work is open, off it with a notch cut for
# each time it was done. The herd's hurts: the jobs pack does not count a tending, so this rule does (a holder's
# tending of a hurt beast of the job's species closes it, through the pack's own done), a beast of that species hit,
# wounded or downed opens it again, and at dawn a pouch back in its keeper's hands is packed fresh.
use("jobs")

TROUBLE_KINDS = ["beast_hungry", "beast_stalks", "beast_prowls", "beast_hunts"]
HURT_KINDS = ["hit", "wounded", "downed"]

def of_species(ctx, eid, species):
    b = ctx.get(eid) if eid else None
    return b is not None and b.state.species == species

def about(ctx, event, species):
    p = event.payload
    if p.get("species") == species or of_species(ctx, event.target, species):
        return True
    for h in p.get("hunters") or []:
        if of_species(ctx, h, species):
            return True
    return False

def show(ctx, job):
    for sign in ctx.find(type="job_token", limit=20):
        if sign.state.job != job.name:
            continue
        if job.state.open:
            look = sign.state.look_open
        else:
            n = int(job.state.done_count or 0)
            look = sign.state.look_closed + ((" " + str(n) + " notches cut in it.") if n else "")
        ctx.patch(sign, {"description": look})

def tending_jobs(ctx):
    return [j for j in ctx.find(type="job", limit=50) if (j.state.done or {}).get("kind") == "tended"]

def tended(ctx, event):
    p = event.payload
    who = ctx.get(p.get("by")) if p.get("by") else None
    if who is None or not p.get("success"):
        return
    for job in tending_jobs(ctx):
        h = (job.state.holders or {}).get(who.id)
        if h is None or not about(ctx, event, (job.state.done or {}).get("species")):
            continue
        n = int(h.get("count") or 0) + 1
        if n >= int((job.state.done or {}).get("count") or 1):
            done(ctx, job, who)
        else:
            ctx.patch(job, {"holders": {who.id: {"count": n}}})

def refill(ctx):
    for pouch in ctx.find(type="medicine", limit=50):
        keeper = pouch.state.refills_with
        if keeper and pouch.parent is not None and pouch.parent.name == keeper and int(pouch.state.doses or 0) < int(pouch.state.refill or 0):
            ctx.patch(pouch, {"doses": int(pouch.state.refill), "description": pouch.state.description_full or pouch.state.description})

def on(ctx, event):
    k = event.kind
    if k == "tended":
        tended(ctx, event)
        return
    if k == "dawn":
        refill(ctx)
        return
    if k in HURT_KINDS:
        for job in tending_jobs(ctx):
            species = (job.state.done or {}).get("species")
            if species and not job.state.open and of_species(ctx, event.target, species):
                reopen(ctx, job, "one of the herd is hurt")
        return
    if k in TROUBLE_KINDS:
        for job in ctx.find(type="job", limit=50):
            species = (job.state.done or {}).get("species")
            if species and not job.state.open and about(ctx, event, species):
                reopen(ctx, job, "the " + species + "s are trouble again")
        return
    job = ctx.get(event.payload.get("job")) if event.payload.get("job") else None
    if job is not None and job.is_a("job"):
        show(ctx, job)
