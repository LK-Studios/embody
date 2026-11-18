"""A seat writes its own bonds: a player or a mind may relate and unrelate a relation its own body is in, of a kind
the world's root lists in `bonds` (a name given, a debt), with a line or two of data. Every other kind, and every
bond that is not its own, stays the host's."""

import pytest

from embody.ops import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def bonded(kinds=("named", "owes", "trusts", "wronged")):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    if kinds:
        gm.patch(w.root_id, {"bonds": list(kinds)})
    sam = eng.session_for_token(gm.invite("player", entity="Prisoner", label="sam")["token"])
    sam.join()
    return eng, w, i, gm, sam


def test_a_seat_writes_and_removes_its_own_bond_of_a_listed_kind():
    eng, w, i, gm, sam = bonded()
    r = sam.relate("owes", ["Guard"], {"what": "a cup of water"})
    assert r["participants"] == [i["Prisoner"], i["Guard"]]  # your own bond: you are in it
    h = w.store.get("hyperedge", w.id, r["relation"])
    assert h["relation"] == "owes" and h["data"] == {"what": "a cup of water"}
    assert w.events(kinds=["related"], limit=1, newest=True)[-1]["actor_id"] == i["Prisoner"]
    sam.unrelate(r["relation"])
    assert w.store.get("hyperedge", w.id, r["relation"]) is None


def test_other_kinds_others_bonds_and_long_data_are_refused():
    eng, w, i, gm, sam = bonded()
    with pytest.raises(Rejected) as e:
        sam.relate("duel", ["Guard"])  # a kind with rules behind it stays the host's
    assert "named" in e.value.hint and "owes" in e.value.alternatives
    theirs = gm.relate("owes", ["Guard", "Hall"], {"what": "rent"})["relation"]
    with pytest.raises(Rejected) as e:
        sam.unrelate(theirs)
    assert "not yours" in e.value.reason
    with pytest.raises(Rejected) as e:
        sam.relate("named", ["Guard"], {"what": "x" * 400})
    assert "line or two" in e.value.reason


def test_a_world_with_no_bonds_lets_no_seat_relate():
    eng, w, i, gm, sam = bonded(kinds=())
    with pytest.raises(Rejected) as e:
        sam.relate("named", ["Guard"])
    assert "no seat" in e.value.reason
