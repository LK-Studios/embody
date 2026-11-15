"""Author hints: after a write, one line for each thing players will hit (a place with no way in, a hidden thing
where people stand, a grant that ends), each saying it may be meant. None when nothing applies."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def test_a_place_with_no_way_gets_a_hint_once_its_ways_had_their_chance_and_none_once_connected():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    assert "hints" not in gm.spawn("place", "Two Rooms", name="Attic")  # just made: its ways come next
    out = gm.patch("Attic", {"description": "Dust and a skylight."})
    assert any(h.startswith("Attic: no way in or out") and h.endswith("ignore this.") for h in out["hints"])
    assert "hints" not in gm.connect("Attic", "Hall")
    assert "hints" not in gm.patch("Attic", {"description": "Dust."})


def test_a_hidden_thing_made_where_someone_stands_says_who_is_there():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    eng.session("nate").join("two-rooms", "Prisoner")
    out = gm.spawn("thing", "Cell", name="Loose stone", state={"hidden": True})
    assert any("1 person is in Cell" in h for h in out["hints"])
    assert "hints" not in gm.spawn("thing", "Hall", name="Spyhole", state={"hidden": True})  # the guard is no one's body
    assert "hints" not in gm.spawn("thing", "Cell", name="Bucket")


def test_a_grant_that_ends_says_so_and_one_that_does_not_is_quiet():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    out = gm.invite("player", entity="Prisoner", label="shibiko", expires=2)
    assert out["hints"] == ["shibiko: this grant stops working in 2 hours, wherever the guest is then. Leave expires "
                            "off unless an end is wanted. If that's meant, or not yours to fix, ignore this."]
    assert "hints" not in gm.invite("player", entity="Guard", label="wren")
