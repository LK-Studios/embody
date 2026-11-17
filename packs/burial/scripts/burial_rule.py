use("burial")
# The burial pack's rule on the root: a death starts the body's decay clock; a scheduled turn moves it on a stage;
# the daily sweep stamps the dead no rule heard die and catches up any turn a timer missed.

def on(ctx, event):
    k = event.kind
    if k == "burial_sweep":
        for b in ctx.find(type="creature", state={"dead": True}, limit=100000):
            if b.state.died_at is None:
                stamp(ctx, b)
            else:
                turn(ctx, b)
        return
    b = ctx.get(event.target) if event.target else None
    if b is None or not b.state.dead or not b.is_a("creature"):
        return
    if k == "burial_decay":
        turn(ctx, b)
    else:
        stamp(ctx, b)
