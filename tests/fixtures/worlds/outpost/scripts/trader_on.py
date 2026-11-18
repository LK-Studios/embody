def on(ctx, event):
    # a shard of ember handed to the trader buys a full skin (a stack buys one a shard): the shard is gone at once,
    # so the d20 rules read it as a trade, not a gift. Anything else she keeps.
    if event.target != ctx.self.id:
        return
    item = ctx.get(event.payload.get("item"))
    buyer = ctx.get(event.payload.get("by"))
    if item is None or buyer is None or item.state.kind != "ember" or ctx.embodied(ctx.self):
        return
    n = ctx.count(item)
    ctx.destroy(item)
    for _ in range(n):
        ctx.spawn("waterskin", buyer, name="Trader's waterskin", state={"left": 3, "given_by": ctx.self.id})
    ctx.emit("traded", target=buyer, reach=1, by=ctx.self.id, got="Trader's waterskin", gave="Emberglass")
