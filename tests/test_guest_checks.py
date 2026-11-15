"""Guest checks: a hand the owner has not vouched for writes no way to reach anyone outside the world, its scripts and
frameless verbs wait for the owner's review, and every script reply carries a lint. The owner's hand, and a grant
the owner vouched for, are free of the first two."""

import pytest

from embody.ops import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms

GOOD = "def apply(ctx):\n    ctx.say(ctx.actor, 'The bars hum.')\n"


def guest(eng, gm, vouched=False):
    inv = gm.invite("author", label="wren", vouched=vouched)
    s = eng.session_for_token(inv["token"])
    s.use("two-rooms")
    return s, inv


@pytest.mark.parametrize("text", ["see https://example.test/x", "find me at wren.gg", "wren@mail.example.com",
                                  "DM me for the map", "my discord is wren", "add me on Steam", "venmo me", "call +1 555 010 9999",
                                  "0x" + "ab" * 20])
def test_a_guest_writes_no_way_out_of_the_world(text):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    g, _ = guest(eng, gm)
    with pytest.raises(Rejected) as r:
        g.spawn("thing", "Cell", name="Note", state={"text": text})
    assert "no way to reach anyone outside" in r.value.reason and "vouch" in r.value.hint
    with pytest.raises(Rejected):
        g.patch("Prisoner", {"dialog": {"hello": text}})
    with pytest.raises(Rejected):
        g.define_script("wren_note", f"def apply(ctx):\n    ctx.say(ctx.actor, {text!r})\n")
    assert gm.spawn("thing", "Cell", name="Note", state={"text": text})  # the owner's own hand


def test_ordinary_words_numbers_and_code_pass():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    g, _ = guest(eng, gm)
    g.spawn("thing", "Cell", name="Tally", state={"text": "Day 12. 3 rats, 1 key. Code 7-3-1? Mr. Bell said so. "
                                                          "Follow me to the well; find me on the ridge; pay me 5 "
                                                          "water. We went.to the gate.Live by it.",
                                                  "layout": {"at": [120.5, 40.25, 0]}, "count": 5551234567})
    g.define_script("wren_hum", "def apply(ctx):\n    n = 5551234567 + 1\n    ctx.say(ctx.actor, 'The bars hum.')\n")


def test_a_guests_script_waits_for_the_owner_and_the_old_one_runs_meanwhile():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    g, _ = guest(eng, gm)
    out = g.define_script("wren_hum", GOOD)
    assert out["pending"] and "review_script" in out["hint"]
    assert [s for s in gm.scripts() if s["id"] == "wren_hum"][0]["by"] == g.pid
    with pytest.raises(Rejected) as r:
        w.script("wren_hum")
    assert "waits for the owner's review" in r.value.reason
    with pytest.raises(Rejected):
        g.review_script("wren_hum")  # not the guest's to approve
    assert gm.review_script("wren_hum")["live"]
    assert w.script("wren_hum") and "pending" not in [s for s in gm.scripts() if s["id"] == "wren_hum"][0]
    g.define_script("wren_hum", GOOD.replace("hum", "sing"))  # a change waits too, and the reviewed one runs
    assert "hum" in w.script("wren_hum").source
    assert gm.review_script("wren_hum", approve=False)["restored"]
    assert "hum" in w.script("wren_hum").source and "pending" not in [s for s in gm.scripts() if s["id"] == "wren_hum"][0]


def test_a_vouched_hand_writes_and_scripts_like_the_owner_and_a_vouch_reaches_an_open_session():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    g, inv = guest(eng, gm)
    with pytest.raises(Rejected):
        g.patch("Hall", {"description": "Plans at https://example.test"})
    assert gm.vouch(inv["id"])["vouched"]
    g.patch("Hall", {"description": "Plans at https://example.test"})
    assert "pending" not in g.define_script("wren_hum", GOOD)
    gm.vouch(inv["id"], on=False)
    assert g.define_script("wren_hum2", GOOD)["pending"]


def test_a_frameless_verb_from_an_unvouched_hand_waits_for_the_owner():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    g, _ = guest(eng, gm)
    assert g.program("Rusty key", "glint", GOOD)["pending"]
    with pytest.raises(Rejected) as r:
        g.review("Rusty key", "glint")
    assert "owner's review" in r.value.reason
    assert gm.review("Rusty key", "glint")["live"]
    assert not gm.program("Rusty key", "shine", GOOD)["pending"]


def test_every_script_reply_carries_a_lint_where_it_applies():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    out = gm.define_script("peek", "def apply(ctx):\n    ctx.remember(ctx.target, 'a cold hand')\n"
                                   "    x = ctx.target.state.get('code')\n")
    assert len(out["lint"]) == 2 and any("memory" in x for x in out["lint"])
    assert "lint" not in gm.define_script("hum", GOOD)
