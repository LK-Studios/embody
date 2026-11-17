use("jobs")
# The jobs you could take here (postings where you stand, promises offered to you) with why not, and the ones you hold.

def apply(ctx):
    me = ctx.actor
    cards = [card(ctx, j, me) for j in reachable(ctx, me)]
    held = [c for c in cards if c.get("held")]
    open_ = [c for c in cards if not c.get("held")]
    if not cards:
        ctx.log("no work is posted here, and nobody has offered you any")
    else:
        ctx.log(str(len(held)) + " held, " + str(len(open_)) + " you could look at")
    return {"held": held, "offered": open_,
            "how": "take_job(job=...) takes one; drop_job gives one up; the world sees the work done and pays it"}
