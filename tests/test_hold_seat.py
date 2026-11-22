"""The owner holds a grant to one seat, or to none, without touching its token (hold_seat): a body that died and waits
for its road back, a cell, a timeout. Its principal is moved into the held body, seats() shows only that one, a join
anywhere else (or as someone new) is refused with the owner's why, the hold outlasts the session, and release gives
the grant its own seats back."""

import pytest

from embody.ops import AUTHOR, Rejected
from tests.test_ops import engine_with_two_rooms


def held_world():
    eng, w, i = engine_with_two_rooms()
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.use("two-rooms")
    for name in ("Prisoner", "Guard"):
        gm.patch(name, {"playable": True})
    w.spawn("person", i["Hall"], "Ghost")
    inv = gm.invite("player", label="Sam")
    sam = eng.session_for_token(inv["token"])
    sam.join("two-rooms", "Prisoner")
    return eng, w, i, gm, sam, inv["id"]


def test_a_held_grant_sits_only_where_the_owner_holds_it():
    eng, w, i, gm, sam, gid = held_world()
    ghost = w.find(name="Ghost", limit=1)[0]["id"]
    out = gm.hold_seat(gid, body="Ghost", why="Your body lies on the road; you wake somewhere else.")
    assert out["ok"] and out["seated"] and w.embodied(ghost)["id"] == sam.pid
    released = [e for e in w.events(kinds=["released"], limit=50) if e["payload"].get("cause") == "held"]
    assert released and released[-1]["target_id"] == i["Prisoner"]
    s = sam.seats()
    assert [r["name"] for r in s["seats"]] == ["Ghost"] and s["held"]["why"].startswith("Your body")
    with pytest.raises(Rejected) as r:
        sam.join("two-rooms", "Guard")
    assert "held" in r.value.reason and r.value.hint.startswith("Your body")
    sam.leave()
    assert sam.join("two-rooms")["you"]["name"] == "Ghost"  # a bare join goes back to the held body
    other = eng.session_for_token(gm.invite("player", label="Ana")["token"])
    sam.leave()
    with pytest.raises(Rejected):
        other.join("two-rooms", "Ghost")  # the held body is kept for the grant held to it
    assert next(g for g in gm.grants() if g["id"] == gid)["held"]["body"] == ghost


def test_a_hold_on_the_body_it_already_sits_in_moves_nothing():
    eng, w, i, gm, sam, gid = held_world()
    before = len(w.events(kinds=["released", "embodied"], limit=500))
    out = gm.hold_seat(gid, body="Prisoner", why="Stay where you lie.")
    assert out["ok"] and w.embodied(i["Prisoner"])["id"] == sam.pid
    assert len(w.events(kinds=["released", "embodied"], limit=500)) == before  # the seat is not churned
    with pytest.raises(Rejected):
        sam.join("two-rooms", "Guard")


def test_held_to_nowhere_then_released():
    eng, w, i, gm, sam, gid = held_world()
    gm.hold_seat(gid, why="A timeout.")
    assert w.principal(sam.pid) is None and sam.seats()["seats"] == []
    with pytest.raises(Rejected) as r:
        sam.join("two-rooms", "Guard")
    assert r.value.hint == "A timeout."
    with pytest.raises(Rejected):
        sam.join("two-rooms")
    gm.hold_seat(gid, release=True)
    assert "held" not in sam.seats() and sam.join("two-rooms", "Guard")["you"]["name"] == "Guard"
    with pytest.raises(Rejected):
        gm.hold_seat(gid, release=True)  # not held now


def test_hold_seat_is_the_owners_and_only_for_players_and_minds():
    eng, w, i, gm, sam, gid = held_world()
    with pytest.raises(Rejected):
        sam.hold_seat(gid, body="Guard")
    owner_grant = gm.invite("owner", label="me")["id"]
    with pytest.raises(Rejected):
        gm.hold_seat(owner_grant, body="Guard")
    sam.leave()
    ana = eng.session_for_token(gm.invite("player", label="Ana")["token"])
    ana.join("two-rooms", "Guard")
    with pytest.raises(Rejected) as r:
        gm.hold_seat(gid, body="Guard")  # someone sits there: evict first
    assert "evict" in r.value.hint
