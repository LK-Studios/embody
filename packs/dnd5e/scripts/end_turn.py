use("common")
use("five")
# End your turn in a fight (the fight's rule hands it on).

def check(ctx):
    me = ctx.actor
    f = my_fight(ctx, me)
    if f is None:
        return "you are in no fight"
    if f.state.turn_of != me.id:
        return "it is not your turn"
    return True

def apply(ctx):
    ctx.log("you end your turn")
    return {"ended": True}
