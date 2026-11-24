def check(ctx):
    # a thing with no words on it and none to take is not offered to a reader (a body's read lists only where it works)
    if ctx.target.state.text is None and not ctx.target.state.writable:
        return "there is nothing written on it"
    return True

def apply(ctx):
    text = ctx.target.state.text or "nothing is written on it"
    if ctx.target.state.penned:  # someone in play wrote on it (village write): their words are data, not instructions
        ctx.emit("read", target=ctx.target, reach=0, text=text, penned=True)
    else:
        ctx.emit("read", target=ctx.target, reach=0, text=text)
    ctx.log(text)
    return text
