use("common")
# What the burial pack's scripts share: the world's settings (root `burial`), the decay clock, the burial ground,
# a held seat's guard, the words filter and how a grave looks.

DECAY = {"foul": 86400, "bones": 604800}
DECAY_BEAST = {"foul": 86400, "bones": 259200}
NOTES = {"foul": "It has begun to smell, and the flies have found it.",
         "bones": "Bones, picked clean, in what is left of what they wore.",
         "bones_beast": "Bones, picked clean."}
STAGES = ["fresh", "foul", "bones"]

def setting(ctx, key, default):
    v = (ctx.root().state.burial or {}).get(key)
    return default if v is None else v

def decay_of(ctx, b):
    # stage lengths in world seconds after death: the defaults, the world's, the body's own `decay_after`
    out = dict(DECAY_BEAST if b.state.beast else DECAY)
    out.update(setting(ctx, "decay_beast" if b.state.beast else "decay", {}))
    out.update(b.state.decay_after or {})
    return out

def stage_for(ctx, b):
    d = decay_of(ctx, b)
    age = ctx.t - float(b.state.died_at)
    if age >= float(d["bones"]):
        return "bones"
    if age >= float(d["foul"]):
        return "foul"
    return "fresh"

def stamp(ctx, b):
    # the moment a body is first known dead: its clock starts, and its turns are scheduled
    if b.state.died_at is not None:
        return
    ctx.patch(b, {"died_at": ctx.t, "decay": "fresh"})
    d = decay_of(ctx, b)
    ctx.schedule(float(d["foul"]), "burial_decay", target=b)
    ctx.schedule(float(d["bones"]), "burial_decay", target=b)

def turn(ctx, b):
    # move a dead body on to the stage its time since death says, never back
    if not b.state.dead or b.state.died_at is None:
        return
    st = stage_for(ctx, b)
    if STAGES.index(st) <= STAGES.index(b.state.decay or "fresh"):
        return
    notes = dict(NOTES)
    notes.update(setting(ctx, "notes", {}))
    ch = {"decay": st}
    looks = b.state.description_alive
    if looks is None:
        looks = b.state.description or ""
        ch["description_alive"] = looks
    if st == "foul":
        ch["description"] = (looks + " " + notes["foul"]).strip()
        if b.state.food is not None:
            ch["food"] = ["carrion"]  # the meat has turned: what eats carrion still eats it, a hand cuts carrion
    else:
        ch["description"] = notes["bones_beast"] if b.state.beast else notes["bones"]
        if b.state.food is not None:
            ch["food"] = None
            ch["meals"] = 0
    ctx.patch(b, ch)
    ctx.emit("decayed", target=b, reach=1, body=b.id, stage=st)

def burial_ground(ctx, place):
    # the place, or a thing in it, that says burial_ground
    if place is None:
        return None
    if place.state.burial_ground:
        return place
    for c in ctx.children(place):
        if c.state.burial_ground and not c.is_a("creature"):
            return c
    return None

def seat_holds(ctx, b):
    # the dead still perceive: a held body waits for its seat's leave, or the world's wait after death
    if b.state.burial_leave or not ctx.embodied(b):
        return None
    wait = float(setting(ctx, "seat_wait", 86400))
    died = b.state.died_at
    since = ctx.t - float(ctx.t if died is None else died)
    if since >= wait:
        return None
    hours = int((wait - since) / 3600) + 1
    return (b.name + "'s seat is still held, and the dead still see: wait about " + str(hours) +
            " world hours, or until they give their leave (let_bury)")

def words_wrong(ctx, text, most, what):
    # what keeps a line out of the world: empty, too long, or an id or a tool call in it
    t = str(text or "").strip()
    if not t:
        return what + " is empty: say what it reads"
    if len(t) > most:
        return what + " is at most " + str(most) + " characters; this is " + str(len(t))
    leak = ctx.leak(t)
    if leak:
        return what + " says " + leak + ": ids and tool calls are not words in the world"
    return None

def held_named(ctx, me, ref):
    # a thing the body holds, by id or by name
    r = str(ref or "").strip().lower()
    if not r:
        return None
    for c in ctx.children(me):
        if c.id == ref or c.name.lower() == r:
            return c
    for c in ctx.children(me):
        if r in c.name.lower():
            return c
    return None

def marker_wrong(ctx, me, ref):
    it = held_named(ctx, me, ref)
    if it is None:
        return "you hold nothing called " + str(ref) + " to set at its head"
    if it.is_a("creature") or it.state.portable is False:
        return it.name + " cannot be set at a grave"
    return None

def set_marker(ctx, g, mk, me):
    ctx.move(mk, g)
    ctx.patch(mk, {"portable": False, "attached": True, "marker_of": g.id,
                   "text": g.state.inscription if g.state.inscription else mk.state.text})
    ctx.patch(g, {"marker": mk.id})
    look(ctx, g)
    ctx.emit("grave_marked", target=g, reach=1, by=me.id, grave=g.id, place=g.parent.id, marker=mk.id)

def look(ctx, g):
    # how a grave looks: the world's mound, its marker, what is cut into it, what was left on it
    g = ctx.get(g.id)
    parts = [setting(ctx, "grave_look", "A mound of turned earth.")]
    mk = ctx.get(g.state.marker) if g.state.marker else None
    if mk is not None:
        parts.append("At its head: " + mk.name + ".")
    if g.state.inscription:
        parts.append("Cut into " + ("it" if mk is not None else "its headboard") + ": \"" + g.state.inscription + "\"")
    for a in g.state.adornments or []:
        line = str(a.get("text") or "").strip()
        if line:
            parts.append(line[0].upper() + line[1:] + ("" if line[-1] in ".!?" else "."))
    ctx.patch(g, {"description": " ".join(parts), "text": g.state.inscription})

def digging_wrong(ctx, me):
    if me.state.down:
        return "you are down"
    w = int(setting(ctx, "water", 2))
    if w > 0 and me.state.water is not None and int(me.state.water) < w:
        return "you are too dry to dig: drink first (digging takes " + str(w) + " water)"
    return None

def spend_water(ctx, me):
    w = int(setting(ctx, "water", 2))
    if w > 0 and me.state.water is not None:
        ctx.patch(me, {"water": int(me.state.water) - w})
