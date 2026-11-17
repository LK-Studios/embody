use("jobs")
# The jobs pack's rule on the root: the world's dusk and dawn say when night jobs count; every other event it hears
# is checked against the jobs someone holds (a deed done, a taker dead); job_due fails a job whose days ran out, and
# job_reopen opens one whose time came round.

def on(ctx, event):
    k = event.kind
    js = ctx.root().state.jobs or {}
    if k == js.get("dusk") or k == js.get("dawn"):
        ctx.patch(ctx.root(), {"jobs": {"night": k == js.get("dusk")}})
        return
    j = ctx.get(event.target) if event.target else None
    if k == "job_reopen":
        if j is not None and j.is_a("job"):
            reopen(ctx, j, event.payload.get("why"))
        return
    if k == "job_due":
        tid = event.payload.get("taker")
        h = (j.state.holders or {}).get(tid) if j is not None and j.is_a("job") else None
        if h is not None and h.get("until") is not None and ctx.t >= float(h["until"]) - 1:
            fail(ctx, j, tid, "window")
        return
    for job in ctx.find(type="job", state={"busy": True}, limit=500):
        holders = job.state.holders or {}
        for tid in list(holders):
            h = holders[tid]
            if h is None:
                continue
            if k in ("killed", "died", "beast_died") and event.target == tid:
                fail(ctx, job, tid, "dead")
                continue
            taker = ctx.get(tid)
            if taker is None or not matches(ctx, job, taker, event):
                continue
            n = int(h.get("count") or 0) + 1
            if n >= int((job.state.done or {}).get("count") or 1):
                done(ctx, job, taker)
            else:
                ctx.patch(job, {"holders": {tid: {"count": n}}})
