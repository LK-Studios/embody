use("common")
use("five")
def on(ctx, event):
    # installed on the root: the dead do nothing; the unconscious do nothing (they roll death saves on their turns);
    # thirst's down can yield, drink or crawl; the incapacitated only talk. A deed wakes the one who does it.
    a = ctx.get(event.actor) if event.actor else None
    if a is None:
        return
    verb = event.payload.get("verb")
    if event.kind == "before_act":
        if a.state.dead:
            ctx.reject("the dead do nothing", "this seat is over; join another or watch")
        if a.state.down and a.state.downed_by == "thirst":
            if verb not in ["yield", "drink", "crawl", "stats"]:
                ctx.reject("you are down from thirst: you can yield, drink or crawl", "act('drink', <skin>) or act('crawl', <place>)")
            return
        if a.state.down:
            if verb not in ["stats"]:
                ctx.reject("you are unconscious" + (" and dying: you roll a death save on each of your turns" if a.state.dying else ", but stable: you wake in a few hours"),
                           "someone may heal you, or tend you (medicine against 10) to stop the dying")
            return
        if verb not in ["talk", "yield", "stats", "end", "escape", "sleep", "wake"] and incapacitated(ctx, a) and not a.state.asleep:
            ctx.reject("you cannot act: " + ", ".join([k for k in conds(ctx, a) if k in INCAP]), "it passes, or someone ends it")
    elif event.kind == "act":
        if a.state.braced and verb != "brace":
            ctx.patch(a, {"braced": False})
        if a.state.asleep and verb not in ["sleep", "wake"]:
            ctx.patch(a, {"asleep": False})
            ctx.emit("woke", target=a, reach=1, by=a.id, why="rose")
        if verb in ["go", "crawl"]:
            here = a.parent
            to = ctx.get(event.payload.get("target")) if event.payload.get("target") else None
            carry = a.state.carry
            if carry and ctx.load(a) > float(carry) / 2 and ((here and here.state.open) or (to and to.state.open)):
                sweat(ctx, a, "heavy_walk")
        elif verb not in ["fight", "heavy_walk"]:
            sweat(ctx, a, verb)
