"""Looks: a body's appearance as data beside its description (src/embody/looks.py). Only the world's rules mark a body;
a reader sees the marks of its band, uncovered; a replaced region's line is the mark's; worn-on marks fade."""

import pytest

from embody.ops import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms

INK = """
def apply(ctx):
    p = ctx.params or {}
    return ctx.mark(ctx.actor, p.get('where'), p.get('what'), p.get('kind') or 'permanent', p.get('band') or 'near',
                    p.get('lasts'))
"""
SCRUB = """
def apply(ctx):
    return ctx.unmark(ctx.actor, ctx.params.get('mark'))
"""


def parlour():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.define_script("ink", INK)
    gm.define_script("scrub", SCRUB)
    gm.define_schema("needle", extends="thing", actions={
        "ink": {"script": "ink", "doc": "Be marked", "params": {"where": "", "what": "", "kind": "", "band": "", "lasts": ""}},
        "scrub": {"script": "scrub", "doc": "Have a mark taken off", "params": {"mark": ""}}})
    gm.spawn("needle", "Hall", name="Needle", state={"portable": False})
    nate = eng.session("nate")
    nate.join("two-rooms", "Prisoner")
    sam = eng.session("sam")
    sam.join("two-rooms", "Guard")
    gm.move("Prisoner", "Hall")
    gm.move("Guard", "Hall")
    return eng, w, gm, nate, sam


def ink(seat, **p):
    return seat.act("ink", "Needle", p)


def seen_lines(seat, name):
    card = next(c for c in seat.perceive()["present"] if c["name"] == name)
    return card["state"].get("looks", [])


def test_a_world_verb_marks_a_body_and_others_see_what_their_band_shows():
    eng, w, gm, nate, sam = parlour()
    r = ink(nate, where="arms", what="a ring of Keth knots inked round the left forearm")
    assert r["result"] == "m1"
    ev = [e for e in r["events"] if e["kind"] == "marked"][0]["payload"]
    assert (ev["where"], ev["kind"], ev["band"]) == ("arms", "permanent", "near")
    ink(nate, where="face", what="a pinprick star under the eye", band="close")
    assert seen_lines(sam, "Prisoner") == ["Arms: a ring of Keth knots inked round the left forearm."]
    mine = nate.perceive()["you"]["state"]["looks"]
    assert mine == ["Face: a pinprick star under the eye.", "Arms: a ring of Keth knots inked round the left forearm."]
    # a coat over the arms hides the knots from others; its wearer still knows them
    gm.spawn("thing", "Prisoner", name="Coat", state={"portable": True, "covers": ["arms", "torso"]})
    assert seen_lines(sam, "Prisoner") == []
    assert "Arms: a ring of Keth knots inked round the left forearm. (covered)" in nate.perceive()["you"]["state"]["looks"]
    theirs = sam.looks("Prisoner")
    assert theirs["marks"] == [] and "head" in theirs["regions"]
    own = {m["where"]: m for m in nate.looks("Prisoner")["marks"]}
    assert own["arms"]["covered"] and not own["face"]["covered"]
    gm.patch("Coat", {"worn": False})  # carried, not worn
    assert seen_lines(sam, "Prisoner")


def test_replaced_takes_the_line_grown_adds_a_region_and_the_checks_hold():
    eng, w, gm, nate, sam = parlour()
    ink(nate, where="legs", what="shins scarred from the salt road")
    ink(nate, where="legs", what="both legs below the knee swapped for geared wheels in a chrome frame", kind="replaced",
        band="far")
    ink(nate, where="legs", what="a maker's stamp on the left wheel")
    ink(nate, where="tail", what="a short jointed tail of glass", kind="grown")
    lines = seen_lines(sam, "Prisoner")
    assert "Legs: both legs below the knee swapped for geared wheels in a chrome frame; a maker's stamp on the left wheel." in lines
    assert "Tail: a short jointed tail of glass." in lines and "tail" in sam.looks("Prisoner")["regions"]
    for p, why in (({"where": "wings", "what": "feathers"}, "has no wings"),
                   ({"where": "arms", "what": "see https://example.com"}, "carries"),
                   ({"where": "arms", "what": "x", "kind": "painted"}, "kind is one of"),
                   ({"where": "arms", "what": "x", "lasts": 2}, "only a worn-on mark lasts")):
        with pytest.raises(Rejected) as r:
            ink(nate, **p)
        assert why in r.value.reason
    # a verb programmed on one thing is not the world's rules, and the owner's patch is
    gm.program("Needle", "smudge", INK)
    with pytest.raises(Rejected) as r:
        nate.act("smudge", "Needle", {"where": "arms", "what": "a smudge"})
    assert "a body's looks change only by the world's rules" in r.value.reason
    gm.patch("Prisoner", {"looks": {"regions": ["head", "torso", "arms", "legs"]}})
    assert gm.inspect("Prisoner")["state"]["looks"]["regions"] == ["head", "torso", "arms", "legs"]


def test_worn_on_fades_and_unmark_takes_one_off_with_events():
    eng, w, gm, nate, sam = parlour()
    ink(nate, where="face", what="red ochre stripes", kind="worn-on", lasts=1)
    mark = ink(nate, where="hands", what="a burn scar across the knuckles")["result"]
    assert "Face: red ochre stripes." in seen_lines(sam, "Prisoner")
    assert sam.looks("Prisoner")["marks"][0]["fades_at"] is not None
    gm.clock(step=86401)
    assert seen_lines(sam, "Prisoner") == ["Hands: a burn scar across the knuckles."]
    r = nate.act("scrub", "Needle", {"mark": mark})
    gone = {e["payload"]["mark"]: e["payload"]["why"] for e in r["events"] if e["kind"] == "unmarked"}
    assert gone == {"m1": "faded", mark: "taken off"}
    assert gm.inspect("Prisoner")["state"]["looks"]["marks"] == {}
    # from another room nobody sees them
    gm.move("Guard", "Cell")
    with pytest.raises(Rejected) as r:
        sam.looks("Prisoner")
    assert "cannot see" in r.value.reason
