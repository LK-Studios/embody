"""Who sits in a body is the host's to know: a guest meets the body, not the person or what stands behind it
(DESIGN.md section 14, "Secrets have owners"). And what a player sees laid out, it sees the size of."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def seated():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    a = eng.session_for_token(gm.invite("player", entity="Prisoner", label="wizard")["token"])
    m = eng.session_for_token(gm.invite("mind", entity="Guard", label="ruhl")["token"])
    a.join()
    a.perceive()
    gm.move("Guard", i["Cell"])
    m.join()
    m.say("Who goes there?")
    return eng, w, i, gm, a, m


def test_a_guest_meets_the_body_not_who_holds_it():
    eng, w, i, gm, a, m = seated()
    b = a.perceive(events=50)
    guard = next(c for c in b["present"] if c["name"] == "Guard")
    assert guard["embodied_by"] == "someone"
    assert b["you"]["embodied_by"] == a.pid  # your own seat is yours to know
    sat = [e for e in b["events"] if e["kind"] == "embodied" and e["actor"] == i["Guard"]]
    assert sat and all("principal" not in e["payload"] and "as" not in e["payload"] for e in sat)
    said = [e for e in b["events"] if e["kind"] == "say" and e["actor"] == i["Guard"]]
    assert said and all(e["by_player"] == "someone" and e["untrusted"] is True for e in said)
    assert m.pid not in str(b) and "ruhl" not in str(b)
    seats = a.seats()["seats"]
    assert seats and all(s["embodied_by"] in (None, "someone", a.pid) for s in seats)
    # the mind meets the player the same way
    mb = m.perceive(events=50)
    assert next(c for c in mb["present"] if c["name"] == "Prisoner")["embodied_by"] == "someone"
    assert a.pid not in str(mb) and "wizard" not in str(mb)


def test_the_host_still_knows_who_sits_where():
    eng, w, i, gm, a, m = seated()
    b = gm.perceive(from_entity="Prisoner", events=50)
    assert next(c for c in b["present"] if c["name"] == "Guard")["embodied_by"] == m.pid
    sat = [e for e in b["events"] if e["kind"] == "embodied" and e["actor"] == i["Guard"]]
    assert sat and sat[-1]["payload"]["principal"] == m.pid
    said = [e for e in b["events"] if e["kind"] == "say" and e["actor"] == i["Guard"]]
    assert said and said[-1]["by_player"] == m.pid


def test_perceive_layout_gives_the_size_of_what_you_see():
    eng, w, i, gm, a, m = seated()
    gm.layout(placements=[{"entity": "Cell", "at": [0, 0, 0], "size": [8, 8, 3]},
                          {"entity": "Prisoner", "at": [1, 1, 0]},
                          {"entity": "Rusty key", "at": [3, 1, 0], "size": [0.3, 0.1, 0.05], "heading": 90},
                          {"entity": "Guard", "at": [2, 4, 0], "radius": 0.4}])
    lay = a.perceive(layout=True)["layout"]
    key = next(r for r in lay["present"] if r["name"] == "Rusty key")
    assert key["size"] == [0.3, 0.1, 0.05] and key["heading"] == 90 and key["distance"] == 2.0
    assert next(r for r in lay["present"] if r["name"] == "Guard")["radius"] == 0.4
    assert "mesh" not in key
