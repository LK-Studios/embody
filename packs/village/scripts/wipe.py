# Wipe chalk off a slate, a board or a door (village write, `writable` "chalk"; or anything whose state is `erasable`),
# held or here: what was chalked on it goes, whoever wrote it, and its `keeps` stays (words painted on, or what the
# text says of the room behind a door). The room sees it wiped; whoever read it keeps what it said.

def check(ctx):
    it = ctx.target
    if it.state.writable != "chalk" and not it.state.erasable:
        return "it does not wipe off: only chalk does"
    holder = it.parent
    here = ctx.actor.parent
    if holder is None or (holder.id != ctx.actor.id and (here is None or holder.id != here.id)):
        return "it is not in your hands or here"
    if str(it.state.text or "").strip() == str(it.state.keeps or "").strip():
        return "there is nothing on it to wipe"
    return True

def apply(ctx):
    it = ctx.target
    ctx.patch(it, {"text": str(it.state.keeps or ""), "hands": None, "penned": None})
    ctx.emit("wiped", target=ctx.actor.parent, reach=1, by=ctx.actor.id, thing=it.id, name=it.name)
    ctx.log("you wipe the " + str(it.name).lower() + " clean")
    return {"wiped": it.id}
