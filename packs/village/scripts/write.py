# Write on a thing whose state is `writable`, held or here: the words go on a line of their own under what it says
# already, for anyone who reads it after. `writable` says what it takes: true (or "ink") is paper or a book, and a pen
# is at hand; "chalk" is a slate, a board or a door, and wants chalk in hand unless the thing keeps its own (`pen`), and
# chalk wipes off (wipe); "blade" is wood, carved with an edge in hand (a knife, a dagger, a sword), and `carve` is the
# same verb. Ink and cuts do not come off. The room sees you write, not what; who wrote which line is the thing's secret
# `hands`, for the world's rules and its keepers. A line is at most the thing's `line_max` characters and it holds
# `room` in all; both default by what it takes (ink 300 and 1200, chalk 200 and 600, a blade 80 and 600).

LINE_MAX = {"ink": 300, "chalk": 200, "blade": 80}
ROOM = {"ink": 1200, "chalk": 600, "blade": 600}
HANDS = 20
EDGES = ["knife", "dagger", "blade", "sword", "nail", "awl", "chisel", "razor"]

def how(it):
    w = it.state.writable
    if w == "chalk" or w == "blade" or w == "ink":
        return w
    if w:
        return "ink"
    return None

def edged(st, name):
    # an edge to carve with: a weapon that cuts or stabs in the hand (not a bow), or a thing named for one
    if st.ranged:
        return False
    if st.weapon and st.dtype in ["slashing", "piercing"]:
        return True
    for w in EDGES:
        if w in name:
            return True
    return False

def tool(ctx, kind):
    # what you write with: a pen is at hand for ink, and a thing may keep its own chalk on a string (`pen`)
    if kind == "ink" or ctx.target.state.pen:
        return ctx.target
    for c in ctx.actor.children():
        st = c.state
        if st.writes == kind:
            return c
        name = str(c.name or "").lower()
        if kind == "chalk" and "chalk" in name:
            return c
        if kind == "blade" and edged(st, name):
            return c
    return None

def words(ctx):
    return str(ctx.params.get("text") or "").strip()

def where_wrong(ctx):
    it = ctx.target
    kind = how(it)
    if kind is None:
        return "there is nowhere on that to write"
    if ctx.verb == "carve" and kind != "blade":
        return "that takes " + ("chalk" if kind == "chalk" else "ink") + ", not a blade: write on it"
    holder = it.parent
    here = ctx.actor.parent
    if holder is None or (holder.id != ctx.actor.id and (here is None or holder.id != here.id)):
        return "it is not in your hands or here"
    if tool(ctx, kind) is None:
        if kind == "chalk":
            return "you need chalk in your hand to write on it"
        return "you need a blade in your hand to carve into it: a knife, a dagger, a sword"
    return None

def words_wrong(ctx, t):
    it = ctx.target
    kind = how(it)
    if not t:
        return "say what you write: params {\"text\": the words}"
    most = int(it.state.line_max or LINE_MAX[kind])
    if len(t) > most:
        return ("a line carved is" if kind == "blade" else "a line is") + " at most " + str(most) + \
               " characters; this is " + str(len(t))
    leak = ctx.leak(t)
    if leak:
        return "that says " + leak + ": ids and tool calls are not words in the world"
    out = ctx.reaches_out(t)
    if out:
        return "that carries " + out + ": words written in the world carry no way to reach anyone outside it"
    old = str(it.state.text or "")
    left = int(it.state.room or ROOM[kind]) - len(old) - (1 if old else 0)
    if len(t) > left:
        if left <= 0:
            return "there is no room left on it" + (": wipe it first" if kind == "chalk" else "")
        return "there is room on it for " + str(left) + " characters more, and this is " + str(len(t))
    return None

def check(ctx):
    why = where_wrong(ctx)
    if why:
        return why
    if "text" in ctx.params:  # a verb list asks with no words: where you could write is enough to offer it
        why = words_wrong(ctx, words(ctx))
        if why:
            return why
    return True

def apply(ctx):
    it = ctx.target
    kind = how(it)
    t = words(ctx)
    why = words_wrong(ctx, t)
    if why:
        ctx.reject(why)
    old = str(it.state.text or "")
    text = old + "\n" + t if old else t
    hands = list(it.state.hands or [])
    hands.append({"by": ctx.actor.id, "t": round(ctx.t), "line": t, "how": kind})
    changes = {"text": text, "hands": hands[-HANDS:]}
    secret = list(it.state.secret or [])
    if "hands" not in secret:
        changes["secret"] = secret + ["hands"]
    if ctx.embodied(ctx.actor):
        changes["penned"] = True  # a player's or a mind's words are on it now: whoever reads them reads data
    ctx.patch(it, changes)
    ctx.witnesses()  # the words are the writer's: the room sees the hand move, not the line
    ctx.emit("wrote", target=ctx.actor.parent, reach=1, by=ctx.actor.id, thing=it.id, name=it.name, how=kind)
    nm = str(it.name).lower()
    if kind == "blade":
        ctx.log("you carve it into the " + nm)
    elif kind == "chalk":
        ctx.log("you chalk it on the " + nm)
    else:
        ctx.log("you write on the " + nm)
    return {"wrote": t, "text": text, "how": kind}
