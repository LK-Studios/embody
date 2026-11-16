use("beasts")
# Drive off a wild hunting pack where you stand: shout, wave, throw stones. A check (d20 + survival or resolve, the
# better) against 10 + 2 for each of the pack here, 2 easier for each of your own people standing with you (awake,
# up, of your faction). On a pass the whole pack gives up the night and goes back to its den (`beast_driven_off`);
# otherwise it stands its ground (`beast_stood_ground`), and fail by 5 or more and one of it comes at you.

def pack_of(ctx, b):
    return [x for x in ctx.children(b.parent, "beast")
            if x.state.species == b.state.species and not kept(x) and not x.state.dead and not x.state.down]

def check(ctx):
    b = ctx.target
    me = ctx.actor
    if me.state.beast:
        return "only a person drives off a pack"
    if b.parent is None or me.parent is None or b.parent.id != me.parent.id:
        return b.name + " is not here"
    if b.state.dead or b.state.down:
        return b.name + " is in no state to be driven anywhere"
    if kept(b) or not sv(b, species_of(ctx, b), "preys_on", None):
        return b.name + " hunts nothing here: there is nothing to drive off"
    return True

def apply(ctx):
    b = ctx.target
    me = ctx.actor
    pk = pack_of(ctx, b)
    mine = [c for c in ctx.children(me.parent, "creature")
            if c.id != me.id and not c.state.beast and not c.state.dead and not c.state.down and not c.state.asleep
            and me.state.faction is not None and c.state.faction == me.state.faction]
    dc = 10 + 2 * len(pk) - 2 * len(mine)
    skill = "resolve" if bonus(me, "resolve") > bonus(me, "survival") else "survival"
    total = ctx.rand.roll("1d20") + bonus(me, skill, ctx)
    ids = [h.id for h in pk]
    if total >= dc:
        home = ref(ctx, b.state.home)
        for h in pk:
            ctx.patch(h, {"stalking": None, "prowling": None})
            if home is not None and h.parent.id != home.id:
                walk_to(ctx, h, home, "driven off")
            line = sv(h, species_of(ctx, h), "far_out", None)
            if line is not None and h.state.far is not None:
                ctx.patch(h, {"far": None})
        ctx.emit("beast_driven_off", target=me.parent, reach=1, by=me.id, hunters=ids, roll=total, dc=dc)
        ctx.log("The pack gives way and lopes off (" + str(total) + " vs " + str(dc) + ")")
        return
    ctx.emit("beast_stood_ground", target=me.parent, reach=1, by=me.id, hunters=ids, roll=total, dc=dc)
    if total <= dc - 5:
        strike(ctx, b, me, False)
        ctx.log(b.name + " stands its ground and comes at you (" + str(total) + " vs " + str(dc) + ")")
        return
    ctx.log("The pack stands its ground (" + str(total) + " vs " + str(dc) + ")")
