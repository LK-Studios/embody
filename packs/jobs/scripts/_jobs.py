use("common")
# What the jobs pack's scripts share: finding a job and its giver, who may take it, whether an event is the work,
# paying it, and opening it again (packs/jobs/pack.py says what a job holds).

def jobs_setting(ctx, key, default):
    v = (ctx.root().state.jobs or {}).get(key)
    return default if v is None else v

def named(ctx, ref, kind):
    # an entity by id, else by its whole name (any case), else None
    if not ref:
        return None
    e = ctx.get(ref)
    if e is not None:
        return e
    low = str(ref).lower()
    for f in ctx.find(type=kind, name=str(ref), limit=20):
        if (f.name or "").lower() == low:
            return f
    return None

def giver_of(ctx, job):
    return named(ctx, job.state.giver, "creature")

def is_giver(job, who):
    g = job.state.giver
    return bool(g) and (g == who.id or str(g).lower() == (who.name or "").lower())

def place_of(ctx, e):
    # the place something is in: itself if it is one, else up its holders
    p = e
    for i in range(8):
        if p is None or p.is_a("place"):
            return p
        p = ctx.parent(p)
    return None

def posted(ctx, job):
    # a posting lies in a place where anyone may read it; a promise is carried
    p = ctx.parent(job)
    return p is not None and p.is_a("place") and not job.state.hidden

def faction_named(ctx, name):
    low = str(name).lower()
    for f in ctx.find(type="faction", limit=50):
        if (f.name or "").lower() == low:
            return f
    return None

def gate_wrong(ctx, job, who):
    # what keeps this person from the job, in words they can act on; None when nothing does
    g = job.state.gate or {}
    want = g.get("standing") or {}
    for fname in want:
        f = faction_named(ctx, fname)
        if f is not None and standing(ctx, who, f) < int(want[fname]):
            return f.name + " do not trust you enough for this yet"
    side = g.get("faction")
    if side and str(who.state.faction or "").lower() != str(side).lower():
        return "this is for " + str(side) + " only"
    ranks = ((who.state.sheet or {}).get("skills") or {})
    need = g.get("skill") or {}
    for sk in need:
        if int(ranks.get(sk) or 0) < int(need[sk]):
            return "this wants more " + sk + " than you have"
    return None

def take_wrong(ctx, job, who):
    if is_giver(job, who):
        return "it is your own job to give"
    holders = job.state.holders or {}
    if who.id in holders:
        return "you hold it already"
    if not job.state.open:
        return "nobody is asking for it now"
    if not posted(ctx, job) and who.id not in (job.state.offers or {}):
        return "it has not been offered to you"
    if len(holders) >= int(job.state.slots or 1):
        return "others have taken it; it may open again"
    return gate_wrong(ctx, job, who)

def reachable(ctx, who):
    # the jobs this person could see: postings where they stand, and any offered to them or held by them
    out = []
    seen = {}
    here = place_of(ctx, who)
    if here is not None:
        for j in ctx.children(here):
            if j.is_a("job") and posted(ctx, j):
                out.append(j)
                seen[j.id] = True
    for j in ctx.find(type="job", limit=500):
        if j.id not in seen and (who.id in (j.state.offers or {}) or who.id in (j.state.holders or {})):
            out.append(j)
            seen[j.id] = True
    return out

def job_named(ctx, who, ref):
    if not ref:
        return None
    low = str(ref).lower()
    for j in reachable(ctx, who):
        if j.id == ref or (j.name or "").lower() == low:
            return j
    for j in reachable(ctx, who):
        if low in (j.name or "").lower():
            return j
    return None

def card(ctx, job, who):
    # a job as a taker reads it: its name, the giver, the terms, and why not when they cannot take it
    g = giver_of(ctx, job)
    out = {"job": job.name, "giver": g.name if g else job.state.giver, "terms": job.state.terms,
           "posted": posted(ctx, job)}
    h = (job.state.holders or {}).get(who.id)
    if h is not None:
        out["held"] = True
        need = int((job.state.done or {}).get("count") or 1)
        out["done_so_far"] = str(int(h.get("count") or 0)) + " of " + str(need)
        if h.get("until") is not None:
            out["days_left"] = round((float(h["until"]) - ctx.t) / ctx.day_seconds(), 1)
        if (job.state.window or {}).get("night"):
            out["when"] = "it counts only at night"
    else:
        why = take_wrong(ctx, job, who)
        if why:
            out["why_not"] = why
    return out

def matches(ctx, job, taker, ev):
    # whether this event is the work the job asks for, done by (or for) this taker
    d = job.state.done or {}
    k = ev.kind
    want = d.get("kind")
    if want and k != want and not (isinstance(want, list) and k in want):
        return False
    p = ev.payload or {}
    t = ctx.get(ev.target) if ev.target else None
    mine = d.get("by_taker")
    if mine is None:
        mine = True
    subjects = [t] if t is not None else []
    if k in ("killed", "downed"):
        if mine and p.get("by") != taker.id:
            return False
    elif k in ("beast_driven_off", "beast_turned_back"):
        # the event lies on the place; what was driven off is the pack in `hunters`, any one of which may be the kind
        if mine and p.get("by") != taker.id:
            return False
        subjects = [h for h in [ctx.get(i) for i in (p.get("hunters") or [])] if h is not None]
    elif k == "given":
        if p.get("by") != taker.id:
            return False
        g = giver_of(ctx, job)
        if not d.get("target") and (g is None or t is None or t.id != g.id):
            return False
        it = ctx.get(p.get("item")) if p.get("item") else None
        if d.get("item") and (it is None or (str(it.name or "").lower() != str(d["item"]).lower()
                                             and str(it.state.kind or "").lower() != str(d["item"]).lower())):
            return False
    elif k == "arrived":
        if p.get("who") != taker.id:
            return False
    elif k == "beast_died":
        if mine:
            return False  # a beast's death names no hand: a job of the taker's own deed waits on killed
    else:
        return False
    if k != "arrived" and (d.get("species") or d.get("type") or d.get("target")):
        hit = False
        for s in subjects:
            if d.get("species") and str(s.state.species or "").lower() != str(d["species"]).lower():
                continue
            if d.get("type") and not s.is_a(d["type"]):
                continue
            if d.get("target") and str(s.name or "").lower() != str(d["target"]).lower() and s.id != d["target"]:
                continue
            hit = True
        if not hit:
            return False
    if d.get("at"):
        if k in ("arrived", "beast_driven_off", "beast_turned_back"):
            where = t
        else:
            where = place_of(ctx, t if t is not None else taker)
        if where is None or (str(where.name or "").lower() != str(d["at"]).lower() and where.id != d["at"]):
            return False
    if (job.state.window or {}).get("night") and not jobs_setting(ctx, "night", False):
        return False
    return True

def pay(ctx, job, taker):
    # the job's floor: things from the giver (or a named store), standing with the giver's people, a deed
    p = job.state.pay or {}
    g = giver_of(ctx, job)
    got = []
    short = []
    for it in p.get("items") or []:
        src = named(ctx, it.get("from"), None) if it.get("from") else g
        want = int(it.get("count") or 1)
        n = 0
        if src is not None:
            for c in ctx.children(src):
                if n >= want:
                    break
                key = str(it.get("kind") or "").lower()
                if str(c.name or "").lower() != key and str(c.state.kind or "").lower() != key:
                    continue
                u = int(c.state.count or 1)
                if u <= want - n:
                    ctx.transfer(c, taker)
                    n = n + u
                else:
                    ctx.transfer(c, taker, want - n)
                    n = want
        if n:
            got.append({"kind": it.get("kind"), "count": n})
        if n < want:
            short.append({"kind": it.get("kind"), "count": want - n})
    stood = None
    if p.get("standing") and g is not None:
        f = faction_of(ctx, g)
        if f is not None:
            shift_standing(ctx, taker, f, int(p["standing"]), "did " + job.name + " for " + g.name)
            stood = {"faction": f.name, "delta": int(p["standing"])}
    grew = None
    dd = p.get("deed") or {}
    if dd.get("skill"):
        n = deed(ctx, taker, dd["skill"], int(dd.get("amount") or 1), job.name)
        grew = {"skill": dd["skill"], "earned": n}
    ctx.emit("job_paid", target=taker, reach=1, job=job.id, giver=g.id if g else None, items=got, standing=stood,
             deed=grew, short=short)

def toward(ctx, job):
    tw = job.state.toward or {}
    e = named(ctx, tw.get("entity"), None) if tw.get("entity") else None
    if e is None or not tw.get("key"):
        return
    ctx.patch(e, {tw["key"]: int(e.state.get(tw["key"]) or 0) + int(tw.get("add") or 1)})

def release(job, taker_id):
    # the holders without this one (None deletes the key in a patch), and whether anyone still holds it
    holders = dict(job.state.holders or {})
    holders[taker_id] = None
    left = 0
    for k in holders:
        if holders[k] is not None:
            left = left + 1
    return holders, left > 0

def fail(ctx, job, taker_id, why):
    if taker_id not in (job.state.holders or {}):
        return
    holders, busy = release(job, taker_id)
    ctx.patch(job, {"holders": holders, "busy": busy or None})
    g = giver_of(ctx, job)
    ctx.emit("job_failed", target=taker_id, reach=1, job=job.id, giver=g.id if g else None, why=why)

def done(ctx, job, taker):
    holders, busy = release(job, taker.id)
    by = dict(job.state.done_by or {})
    by[taker.id] = int(by.get(taker.id) or 0) + 1
    ch = {"holders": holders, "busy": busy or None, "done_by": by, "done_count": int(job.state.done_count or 0) + 1}
    rep = job.state.repeat or "once"
    if rep != "always":
        # closed to newcomers (and old offers) until it opens again; anyone still holding it may still finish
        ch["open"] = False
        offers = dict(job.state.offers or {})
        for k in offers:
            offers[k] = None
        ch["offers"] = offers
    if isinstance(rep, dict) and rep.get("every_days"):
        ctx.schedule(float(rep["every_days"]) * ctx.day_seconds(), "job_reopen", target=job, why="its time came round")
    ctx.patch(job, ch)
    g = giver_of(ctx, job)
    ctx.emit("job_done", target=taker, reach=1, job=job.id, giver=g.id if g else None)
    pay(ctx, job, taker)
    toward(ctx, job)

def reopen(ctx, job, why):
    # a world rule's call, or the job's own time coming round: open again, to postings and to new offers
    if job.state.open:
        return
    ctx.patch(job, {"open": True})
    ctx.emit("job_reopened", target=job, reach=1, job=job.id, why=str(why or ""))
