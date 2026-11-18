"""wait(since=N) reads from N, whatever the cursor says: a second waiter on the same principal (or a watcher catching
up) gets every event after N it could perceive, though the first waiter already moved the cursor past them. And a
busy scene longer than one batch comes in batches: the cursor stops at the last event returned, never past the rest."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def scene():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.move("Prisoner", "Hall")
    sam = eng.session("sam")
    sam.join("two-rooms", "Prisoner")
    sam.wait(timeout=0)
    return eng, w, i, sam


def said(b):
    return [e["payload"]["text"] for e in b["events"] if e["kind"] == "say"]


def test_wait_since_returns_what_another_wait_already_took():
    eng, w, i, sam = scene()
    before = w.store.next_seq(w.id) - 1
    for n in range(3):
        w.say(i["Guard"], f"line {n}", reach=1)
    assert said(sam.wait(timeout=0)) == ["line 0", "line 1", "line 2"]  # the first waiter moves the cursor
    assert said(sam.wait(timeout=0)) == []
    assert said(sam.wait(timeout=0, since=before)) == ["line 0", "line 1", "line 2"]  # the second still gets them


def test_a_scene_longer_than_a_batch_comes_in_batches():
    eng, w, i, sam = scene()
    for n in range(60):
        w.say(i["Guard"], f"line {n}", reach=1)
    first = sam.wait(timeout=0)
    assert first.get("more") and len(first["events"]) == 50
    rest = sam.wait(timeout=0)
    assert not rest.get("more")
    assert said(first) + said(rest) == [f"line {n}" for n in range(60)]
