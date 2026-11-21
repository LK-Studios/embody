"""Verbs named by data (asked by the Glass Reach host, 2026-11-21): an action `named_by` a state key opens out into one
verb per entry of that map on a body, each laid over the world's catalogue on the root, with overlays (its script
among them) picked by the entry's fields. grant_verb and take_verb give and take one by name, the world's keepers'
only; guide('<topic>') lists the catalogue. The map is rules-only on a body, so no code gives a body a verb of this
kind: a world's gifts were verbs programmed on their holders, which may not write hp, and every one failed."""

import pytest

from embody.ops import Rejected, call
from tests.test_grants import owner
from tests.test_limits import builder
from tests.test_ops import engine_with_two_rooms

SOOTHE = """
def check(ctx):
    g = ctx.named_entry(ctx.actor, "boons", ctx.verb)
    return True if ctx.target.state.hp < 6 else "they are whole"

def apply(ctx):
    g = ctx.named_entry(ctx.actor, "boons", ctx.verb)
    ctx.patch(ctx.target, {"hp": min(6, ctx.target.state.hp + int(g.get("amount") or 1))})
    return {"healed": g.get("amount"), "verb": ctx.verb}
"""
SHOW = """
def apply(ctx):
    ctx.emit("shown", target=ctx.actor, reach=1, what=ctx.named_entry(ctx.actor, "boons", ctx.verb).get("words"))
"""
CATALOGUE = {"soothe": {"kind": "mend", "amount": 1, "words": "Ease someone's hurt here, or your own"},
             "glow": {"kind": "show", "words": "A light about you, seen by those here"}}


def world():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.define_script("boon_mend", SOOTHE)
    gm.define_script("boon_show", SHOW)
    gm.define_schema("hero", extends="creature", state={"hp": 6, "max_hp": 6},
                     actions={"boon": {"script": "boon_show", "duration": 2, "doc": "a boon",
                                       "named_by": {"key": "boons", "catalogue": "boon_catalogue", "topic": "boons",
                                                    "guide": "Boons: what a hero can do that no skill teaches.",
                                                    "by": {"kind": {"mend": {"script": "boon_mend", "targets": "creature",
                                                                             "scope": "here", "self": True}}}}}})
    gm.patch(w.root_id, {"boon_catalogue": CATALOGUE})
    gm.spawn("hero", "Hall", "Ana", state={"playable": True})
    gm.spawn("hero", "Hall", "Bo", state={"hp": 2})
    ana = eng.session("ana")
    ana.join("two-rooms", "Ana")
    return eng, w, gm, ana


def hp(gm, name):
    return gm.inspect(name)["state"]["hp"]


def test_a_granted_verb_shows_by_its_own_name_and_runs_its_kinds_script():
    eng, w, gm, ana = world()
    assert not any(a["verb"] in ("soothe", "boon") for a in ana.perceive()["affordances"])
    r = gm.grant_verb("Ana", "soothe", {"amount": 3})
    assert r["entry"] == {**CATALOGUE["soothe"], "amount": 3} and r["holds"] == ["soothe"]
    gm.grant_verb("Ana", "glow")
    aff = {(a["verb"], a["target_name"]): a for a in ana.perceive()["affordances"]}
    assert aff[("soothe", "Bo")]["doc"] == CATALOGUE["soothe"]["words"] and ("soothe", "Ana") in aff
    assert ("glow", None) in aff and "boon" not in {v for v, _ in aff}
    assert gm.inspect("Ana")["actions"]["soothe"]["named"] == "boons"
    assert ana.act("soothe", "Bo")["result"] == {"healed": 3, "verb": "soothe"} and hp(gm, "Bo") == 5
    ana.act("glow")
    assert w.events(kinds=["shown"], limit=5)[-1]["payload"]["what"] == CATALOGUE["glow"]["words"]
    gm.grant_verb("Ana", "soothe", {"amount": None})  # back to the catalogue's
    assert gm.inspect("Ana")["state"]["boons"]["soothe"] == {}
    with pytest.raises(Rejected, match="no action 'boon'"):
        ana.act("boon", "Bo")
    gm.take_verb("Ana", "glow")
    gm.grant_verb("Bo", "glow")
    with pytest.raises(Rejected, match="no action 'glow'"):
        ana.act("glow", "Bo")  # Bo's gift is Bo's to use, never one done to Bo by whoever is near


def test_grant_and_take_say_what_there_is_and_refuse_what_is_not():
    eng, w, gm, ana = world()
    with pytest.raises(Rejected) as r:
        gm.grant_verb("Ana", "fireball")
    assert "catalogue" in r.value.reason and "glow, soothe" in r.value.hint and "guide('boons')" in r.value.hint
    with pytest.raises(Rejected, match="no verbs by name"):
        gm.grant_verb("Guard", "soothe")
    gm.grant_verb("Ana", "glow")
    assert gm.take_verb("Ana", "glow")["taken"] and "boons" not in gm.inspect("Ana")["state"]
    with pytest.raises(Rejected) as r:
        gm.take_verb("Ana", "glow")
    assert "holds no" in r.value.reason
    g = gm.guide("boons")
    assert g["text"].startswith("Boons:") and "soothe: Ease someone's hurt" in g["text"] and "grant_verb" in g["text"]
    assert g["catalogue"] == CATALOGUE


def test_nobody_but_the_rules_and_the_keepers_gives_a_verb_of_this_kind():
    eng, w, gm, ana = world()
    assert call(ana, "grant_verb", body="Ana", name="soothe")["ok"] is False  # a player has no such op
    b, inv = builder(eng, gm)
    b.use("two-rooms")
    for op in ("grant_verb", "take_verb"):
        assert call(b, op, body="Ana", name="soothe")["ok"] is False
    pre = inv["limits"]["scripts"]
    b.define_script(f"{pre}mint", 'def apply(ctx):\n    ctx.patch(ctx.actor, {"gift_book": {"soothe": {}}})\n')
    b.define_schema(f"{pre}idol", extends="thing", actions={"touch": {"script": f"{pre}mint", "reach": "near"}})
    b.spawn(f"{pre}idol", "Hall", name="Idol")
    r = call(ana, "act", verb="touch", target="Idol")
    assert r["ok"] is False and "gifts are given only by the world's rules" in r["reason"]
    r = call(b, "patch", entity="Bo", changes={"gift_uses": {}})
    assert r["ok"] is False and "may not write gift_uses" in r["reason"]
