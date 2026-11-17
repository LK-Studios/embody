# The jobs rule (see _reach_job.py): every job thing in the world, on the events it names. Trouble about its beasts opens
# it again; a taker's deed in its window finishes it, pays them, cuts their mark on the record and closes it until the
# trouble comes back; a taker who lets it lie lapse_days gives it back without cost.
use("reach_job")

TROUBLE_KINDS = ["beast_hungry", "beast_stalks", "beast_prowls", "beast_hunts"]
DONE_KINDS = ["downed", "killed", "beast_driven_off", "beast_turned_back"]

def about(ctx, event, species):
    p = event.payload
    if p.get("species") == species:
        return True
    if of_species(ctx, event.target, species):
        return True
    for h in p.get("hunters") or []:
        if of_species(ctx, h, species):
            return True
    return False

def offer(ctx, thing, j):
    j["open"] = True
    ctx.patch(thing, {"job": j, "description": line(j, "look_open")})
    giver = ctx.get(j.get("giver"))
    ctx.emit("job_offered", target=thing.parent, reach=1, giver=j.get("giver"), job=j.get("id"),
             text=line(j, "opened", None, giver) if giver else "")

def finish(ctx, thing, j, who, how):
    giver = ctx.get(j.get("giver"))
    pay = j.get("pay") or {}
    f = faction_named(ctx, j.get("faction")) if j.get("faction") else None
    if f is not None and int(pay.get("standing") or 0) and who.state.faction != f.name:
        shift_standing(ctx, who, f, int(pay.get("standing")), line(j, "pay_why", who, giver))
    if pay.get("skill"):
        deed(ctx, who, pay.get("skill"), int(pay.get("deed") or 1), line(j, "pay_why", who, giver))
    ledger = list(j.get("ledger") or [])
    ledger.append({"who": who.id, "name": who.name, "day": int(ctx.t // 86400) + 1, "how": how})
    others = [t for t in taker_ids(j) if t != who.id]
    j["ledger"] = ledger[-50:]
    j["takers"] = []
    j["open"] = False
    ctx.patch(thing, {"job": j, "description": line(j, "look_closed") + " " + str(len(ledger)) + " notches cut in it."})
    ctx.emit("job_done", target=who, reach=1, by=who.id, giver=j.get("giver"), job=j.get("id"), how=how,
             text=line(j, "done", who, giver))
    if giver is not None and (giver.parent is None or who.parent is None or giver.parent.id != who.parent.id):
        ctx.emit("job_done", target=giver, reach=0, by=who.id, giver=giver.id, job=j.get("id"), how=how)
    for t in others:
        ctx.emit("job_ended", target=t, reach=0, giver=j.get("giver"), job=j.get("id"), done_by=who.id)

def on(ctx, event):
    k = event.kind
    for thing in ctx.find(type="job_token", limit=20):
        j = job_of(thing)
        species = j.get("species")
        if not species:
            continue
        if k in TROUBLE_KINDS and not j.get("open") and about(ctx, event, species):
            offer(ctx, thing, j)
            continue
        takers = taker_ids(j)
        if k == "dawn" and takers:
            days = int(j.get("lapse_days") or 3) * 86400
            keep = []
            for d in j.get("takers") or []:
                if ctx.t - float(d.get("t") or 0) >= days:
                    ctx.emit("job_lapsed", target=d.get("who"), reach=0, giver=j.get("giver"), job=j.get("id"))
                else:
                    keep.append(d)
            if len(keep) != len(takers):
                j["takers"] = keep
                ctx.patch(thing, {"job": j})
            continue
        if k not in DONE_KINDS or not takers or not in_window(ctx, j):
            continue
        by = event.payload.get("by")
        if by not in takers:
            continue
        if k in ("downed", "killed"):
            if not of_species(ctx, event.target, species):
                continue
            how = ("killed " if k == "killed" else "brought down ") + ctx.get(event.target).name
        elif not about(ctx, event, species):
            continue
        else:
            how = "drove them off" if k == "beast_driven_off" else "turned them from the herd"
        finish(ctx, thing, j, ctx.get(by), how)
