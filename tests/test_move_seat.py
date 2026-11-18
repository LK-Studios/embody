"""A rule moves a seat (ctx.move_seat): whoever holds the acting body now holds another one nobody holds, at once,
with no offer and no claim. The old body is let go, the grant follows the mind, the notes go with it unless the rule
says they stay, and a body someone holds, one that is not seatable, or a script under a grant's limits is refused."""

import pytest

from embody.ops import Rejected
from embody.world import Ctx
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms

TRANSFER = ("def apply(ctx):\n"
            "    return ctx.move_seat(ctx.find(name=ctx.params.get('into'))[0], notes=ctx.params.get('notes', True))\n")


def rig_world():
    eng, w, i = engine_with_two_rooms()
    w.define_script("transfer", TRANSFER)
    w.define_schema("rig", extends="thing", actions={"transfer": {"script": "transfer", "doc": "Go into another body"}})
    w.define_schema("chassis", extends="creature", state={"seatable": True})
    i["Rig"] = w.spawn("rig", i["Cell"], "Rig")
    i["Chassis"] = w.spawn("chassis", i["Cell"], "Chassis")
    i["Fly"] = w.spawn("chassis", i["Cell"], "Fly")
    gm = owner(eng)
    g = gm.invite("player", entity="Prisoner", label="aaron")
    aaron = eng.session_for_token(g["token"])
    aaron.join()
    return eng, w, i, gm, aaron, g


def test_a_rule_moves_the_seat_and_the_old_body_is_let_go():
    eng, w, i, gm, aaron, g = rig_world()
    aaron.remember("the guard sleeps at the second bell")
    aaron.act("transfer", "Rig", params={"into": "Chassis"})
    assert aaron.perceive()["you"]["id"] == i["Chassis"]
    assert w.embodied(i["Prisoner"]) is None and w.embodied(i["Chassis"])["id"] == aaron.pid
    assert "second bell" in str(w.need(i["Chassis"])["state"]["memory"])  # the notes are the mind's
    assert not w.need(i["Prisoner"])["state"].get("memory")
    kinds = [(e["kind"], e["target_id"]) for e in w.events(kinds=["released", "embodied"], limit=5, newest=True)]
    assert kinds[-2:] == [("released", i["Prisoner"]), ("embodied", i["Chassis"])]

    aaron.act("transfer", "Rig", params={"into": "Fly"})  # and on again, from the new body
    assert aaron.perceive()["you"]["id"] == i["Fly"] and w.embodied(i["Chassis"]) is None

    again = eng.session_for_token(g["token"])  # a fresh session of the same grant sits in the body it moved to
    assert again.join()["you"]["id"] == i["Fly"]


def test_notes_may_stay_behind():
    eng, w, i, gm, aaron, g = rig_world()
    aaron.remember("the key is under the third stone")
    aaron.act("transfer", "Rig", params={"into": "Chassis", "notes": False})
    assert "third stone" in str(w.need(i["Prisoner"])["state"]["memory"])
    assert not w.need(i["Chassis"])["state"].get("memory")


def test_a_held_or_unseatable_body_is_refused_and_nothing_moves():
    eng, w, i, gm, aaron, g = rig_world()
    guard = eng.session("guard-mind")
    gm.patch("Chassis", {"seatable": True})
    guard.join("two-rooms", "Chassis")
    with pytest.raises(Rejected) as r:
        aaron.act("transfer", "Rig", params={"into": "Chassis"})
    assert "already held" in str(r.value)
    with pytest.raises(Rejected) as r:
        aaron.act("transfer", "Rig", params={"into": "Guard"})
    assert "not seatable" in str(r.value)
    assert w.embodied(i["Prisoner"])["id"] == aaron.pid


def test_a_script_under_a_grants_limits_cannot_move_seats():
    eng, w, i, gm, aaron, g = rig_world()
    ctx = Ctx(w, actor=i["Prisoner"], target=None, owner=None, params={}, event=None, verb=None, caused_by=None, seed=1)
    ctx._limits = {"under": i["Hall"]}
    with pytest.raises(Rejected) as r:
        ctx.move_seat(i["Chassis"])
    assert "limits" in r.value.reason
