# Dice (Nate 2026-11-17, "introduce gambling and play into the world"): a pair of bone dice anyone can throw. The
# throw is loud enough for the room: everyone here sees the faces. What is staked on it is the players' own business,
# made with say and give; the dice only fall.

def check(ctx):
    d = ctx.target
    if d.parent != ctx.actor.id and d.parent != ctx.actor.parent:
        return "pick up the dice, or stand where they lie, to throw them"
    return True

def apply(ctx):
    faces = [ctx.rand.randint(1, int(ctx.target.state.sides or 6)) for _ in range(int(ctx.target.state.dice or 2))]
    total = sum(faces)
    shown = " and ".join(str(f) for f in faces)
    ctx.emit("rolled", target=ctx.target, reach=1, by=ctx.actor.id, faces=faces, total=total)
    ctx.emit("scene", target=ctx.actor.parent, reach=1,
             text=ctx.actor.name + " shakes the dice and throws: " + shown + (", double " + str(faces[0]) + "s" if len(set(faces)) == 1 and len(faces) > 1 else "") + ".")
    return {"faces": faces, "total": total}
