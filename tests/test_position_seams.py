"""Three seams in positions a second world's playtest found: a body made from a template stands somewhere of its own
(verify does not flag it later), `at` in a patch places the entity instead of writing a state key, and a quiet move
may give a body with no spot its first one."""

import pytest

from embody.layout import ground
from embody.ops import Rejected
from tests.test_positions import _laid


def test_a_template_newcomer_gets_its_own_spot_and_verify_finds_nothing(tmp_path):
    eng, gm = _laid_with_template(tmp_path, {"type": "person", "place": "Ashford Square"})
    guest = eng.session_for_token(gm.invite("player", label="wren")["token"])
    me = guest.join(template="villager", name="Wren")["you"]["id"]
    assert eng.world("ferry-at-dusk").need(me)["state"]["layout"]["at"]  # its own spot, not the square's centre
    assert not [p for p in gm.verify(under="Ashford Square", limit=200)["page"] if p["id"] == me]


def test_a_template_may_name_where_newcomers_arrive_and_a_bad_name_refuses_before_anyone_is_made(tmp_path):
    eng, gm = _laid_with_template(tmp_path / "a", {"type": "person", "place": "Ashford Square", "at": "the notice board"})
    guest = eng.session_for_token(gm.invite("player", label="wren")["token"])
    me = guest.join(template="villager", name="Wren")["you"]["id"]
    assert ground(gm.measure(me)["a"]["at"], [-10, 0, 0]) <= 4

    eng2, gm2 = _laid_with_template(tmp_path / "b", {"type": "person", "place": "Ashford Square", "at": "the gallows"})
    g2 = eng2.session_for_token(gm2.invite("player", label="moss")["token"])
    with pytest.raises(Rejected):
        g2.join(template="villager", name="Moss")
    assert not eng2.world("ferry-at-dusk").find(name="Moss")


def test_at_in_a_patch_places_the_entity_and_writes_no_state_key(tmp_path):
    eng, gm = _laid(tmp_path)
    out = gm.patch("Mara", {"at": "the well", "mood": "tired"})
    assert "at" not in out["state"] and out["state"]["mood"] == "tired"
    assert ground(gm.measure("Mara")["a"]["at"], [5, 5, 0]) <= 3
    with pytest.raises(Rejected) as r:
        gm.patch("Mara", {"at": "the gallows", "mood": "cross"})
    assert "the well" in r.value.hint
    assert gm.inspect("Mara")["state"]["mood"] == "tired"  # a bad name changes nothing


def test_a_quiet_move_may_give_a_body_with_no_spot_its_first_one(tmp_path):
    eng, gm = _laid(tmp_path)
    gm.spawn("thing", "Pell's Mill", "Crate")
    gm.move("Crate", "Ashford Square", quiet=True, at="the notice board")
    assert ground(gm.measure("Crate")["a"]["at"], [-10, 0, 0]) <= 4
    with pytest.raises(Rejected) as r:  # now it has one, and a quiet move keeps it
        gm.move("Crate", "Pell's Mill", quiet=True, at=[100, 5, 0])
    assert "keeps the spot" in r.value.reason


def _laid_with_template(tmp, template):
    tmp.mkdir(exist_ok=True)
    eng, gm = _laid(tmp)
    w = eng.world("ferry-at-dusk")
    gm.patch(w.root_id, {"templates": {"villager": template}})
    return eng, gm
