# The Reach's side of its jobs (the jobs pack keeps, checks and pays them, packs/jobs/pack.py): trouble about a job's
# beasts opens it again, and a job's sign shows it, on its peg while the work is open, off it with a notch cut for
# each time it was done.
use("jobs")

TROUBLE_KINDS = ["beast_hungry", "beast_stalks", "beast_prowls", "beast_hunts"]

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

def on(ctx, event):
    k = event.kind
    if k in TROUBLE_KINDS:
        for job in ctx.find(type="job", limit=50):
            species = (job.state.done or {}).get("species")
            if species and not job.state.open and about(ctx, event, species):
                reopen(ctx, job, "the " + species + "s are trouble again")
        return
    job = ctx.get(event.payload.get("job")) if event.payload.get("job") else None
    if job is not None and job.is_a("job"):
        show(ctx, job)
