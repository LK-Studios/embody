"""A sleeper's own deed wakes it in the core, with no pack's rule needed; and perceive names the landmarks of the place
a body stands in, with the verb that walks to one (players looked for it and did not find it)."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def test_a_sleepers_own_deed_wakes_it():
    eng, w, i = engine_with_two_rooms()
    w.patch(i["Guard"], {"asleep": True})
    w.emit("act", actor=i["Guard"], target=i["Guard"], payload={"verb": "look"})
    assert not w.get(i["Guard"])["state"]["asleep"]
    assert w.events(kinds=["woke"], newest=True, limit=1)[-1]["payload"] == {"by": i["Guard"], "why": "rose"}
    w.patch(i["Guard"], {"asleep": True})
    w.emit("act", actor=i["Guard"], target=i["Guard"], payload={"verb": "sleep"})
    assert w.get(i["Guard"])["state"]["asleep"]  # lying down is not a deed that wakes


def test_perceive_names_the_landmarks_here_and_how_to_reach_one():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.layout(placements=[{"entity": i["Hall"], "landmarks": {"the well": {"at": [2, 2, 0], "radius": 2}}}])
    gm.move("Prisoner", "Hall")
    sam = eng.session("sam")
    sam.join("two-rooms", "Prisoner")
    lm = sam.perceive()["landmarks"]
    assert lm["here"] == ["the well"] and 'step(to="the well")' in lm["how"]
    gm.move("Prisoner", "Cell")
    assert "landmarks" not in sam.perceive()
