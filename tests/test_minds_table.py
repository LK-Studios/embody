"""The minds table (minds()): what a host watches when it runs many minds. Each character a mind runs or should, its
seat, how long its mind has been quiet, the players with it, and a player's line it has not answered."""

import pytest

from embody.ops import AUTHOR, Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def test_the_minds_table_shows_seats_quiet_minds_and_players_owed_an_answer():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch("Guard", {"brief": "You keep the hall."})
    gm.patch("Prisoner", {"brief": "You want out."})
    inv = gm.invite("mind", entity="Guard", label="guard mind")
    mind = eng.session_for_token(inv["token"])
    mind.use("two-rooms")
    mind.join()
    gm.move("Prisoner", "Hall")
    sam = eng.session("sam")
    sam.join("two-rooms", "Prisoner")  # a player on a body that had a brief: the player's now

    r = gm.minds()
    guard = next(m for m in r["minds"] if m["name"] == "Guard")
    assert guard["seated"] and guard["label"] == "guard mind" and guard["players_here"] == ["Prisoner"]
    assert "owed" not in guard and r["alerts"] == []
    assert "Prisoner" not in {m["name"] for m in r["minds"]}  # held by a player, not a character

    sam.say("Guard, open the gate", to="Guard")
    gm.clock(step=60)
    r = gm.minds(owed_min=0)  # waiting at all counts, at owed_min=0
    guard = next(m for m in r["minds"] if m["name"] == "Guard")
    assert guard["owed"]["by"] == "Prisoner" and "open the gate" in guard["owed"]["text"]
    assert any("Prisoner has waited" in a for a in r["alerts"])
    mind.say("Not tonight.")
    assert "owed" not in next(m for m in gm.minds()["minds"] if m["name"] == "Guard")

    mind.leave()
    r = gm.minds()
    assert any("guard mind" in a and "holds no seat" in a for a in r["alerts"])
    with pytest.raises(Rejected, match="minds is not open to a player"):
        sam.minds()


def test_a_character_with_no_mind_that_players_talk_to_is_an_alert():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.patch("Guard", {"brief": "You keep the hall."})
    gm.move("Prisoner", "Hall")
    sam = eng.session("sam")
    sam.join("two-rooms", "Prisoner")
    sam.say("Guard, which way out?", to="Guard")
    r = gm.minds()
    guard = next(m for m in r["minds"] if m["name"] == "Guard")
    assert guard["mind"] is None and not guard["seated"]
    assert any(a.startswith("Guard: no mind") for a in r["alerts"])
