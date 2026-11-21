"""A frame with `review: "writes"` (asked by the Glass Reach host, 2026-11-21): a verb it made waits for the owner's review
as with `review: true`, but until then it runs on a look-only trial. It may read and answer the one who used it; any
write ends the run and the act rolls back, and its machine's secret keys stay sealed, so what the review guards (a
codex) is not read before the owner says yes. `review: true` still stops every verb until review."""

from embody.ops import call
from tests.test_maker import HAIL, yard

LOOK = """
def apply(ctx):
    ctx.log("the cart's plate reads " + str(ctx.self.state.plate))
    return [ctx.self.state.plate, ctx.self.state.codex]
"""


def framed(review):
    eng, w, gm, sam, nate = yard()
    gm.patch("Cart", {"plate": "CART-9", "codex": "the old words", "secret": ["codex"]})
    gm.patch("Wright's frame", {"maker": {"review": review, "max_scripts": 3}})
    sam.act("take", "Wright's frame")
    return eng, w, gm, sam, nate


def test_a_verb_waiting_for_review_may_look_and_reads_no_secret():
    eng, w, gm, sam, nate = framed("writes")
    assert sam.program("Cart", "read_plate", LOOK)["pending"]
    assert nate.programs("Cart")["verbs"][0]["pending"] is True
    aff = [a for a in nate.perceive()["affordances"] if a["verb"] == "read_plate"]
    assert aff and aff[0]["trial"] is True
    assert "trial" in nate.inspect("Cart")["actions"]["read_plate"]
    res = nate.act("read_plate", "Cart")
    assert res["trial"] is True and res["untrusted"]
    assert res["result"] == ["CART-9", None]  # the codex stays sealed on trial
    assert res["logs"] == ["the cart's plate reads CART-9"]
    gm.review("Cart", "read_plate")
    res = nate.act("read_plate", "Cart")
    assert "trial" not in res and res["result"] == ["CART-9", "the old words"]  # approved, it reads its machine in full


def test_a_verb_waiting_for_review_that_writes_is_refused_and_nothing_changes():
    eng, w, gm, sam, nate = framed("writes")
    sam.program("Cart", "hail", HAIL)
    seq = w.store.next_seq(w.id)
    r = call(nate, "act", verb="hail", target="Cart")
    assert r["ok"] is False and "may only look" in r["reason"] and "review" in r["hint"]
    assert w.find(name="Cart")[0]["state"].get("hailed") is None
    assert [e["kind"] for e in w.events(seq - 1, limit=10)] == ["act_refused"]  # rolled back whole, its say with it
    gm.review("Cart", "hail")
    nate.act("hail", "Cart")
    assert w.find(name="Cart")[0]["state"]["hailed"] == 1


def test_review_true_still_stops_every_verb_until_the_owner_looks():
    eng, w, gm, sam, nate = framed(True)
    sam.program("Cart", "read_plate", LOOK)
    assert not any(a["verb"] == "read_plate" for a in nate.perceive()["affordances"])
    r = call(nate, "act", verb="read_plate", target="Cart")
    assert r["ok"] is False and "waits for the owner's review" in r["reason"] and "may only look" not in r["reason"]
