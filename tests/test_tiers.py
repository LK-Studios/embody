"""Tiers: a world grown to full depth (universe, galaxy, planet, region) under its root. A tier needs no spot; one with a
frame starts a frame, so what is under it is placed there; a quiet move regroups places into it with their spots kept
and nobody told; the map and the ruler stay inside one frame; a region's ambient reaches the places in it."""

import pytest

from embody.ops import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def grown():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    gm.layout(frame={"units": "m"}, placements=[{"entity": "Cell", "at": [0, 0, 0], "radius": 4},
                                                 {"entity": "Hall", "at": [20, 0, 0], "size": [12, 8]}])
    gal = gm.spawn("place", "Two Rooms", name="The Near Stars", state={"tier": "galaxy"})["id"]
    planet = gm.spawn("place", gal, name="Fulgar", state={"tier": "planet", "frame": {"units": "km"}})["id"]
    region = gm.spawn("place", planet, name="The Reach", state={"tier": "region", "ambient": {"heat": "dry heat"}})["id"]
    gm.layout(placements=[{"entity": region, "frame": {"units": "m"}, "at": [120, 40, 0]}])
    return eng, gm, i, gal, planet, region


def test_a_quiet_move_regroups_places_into_a_region_keeping_their_spots_and_telling_no_one():
    eng, gm, i, gal, planet, region = grown()
    nate = eng.session("nate")
    nate.join("two-rooms", "Prisoner")
    nate.perceive()
    for p in ("Cell", "Hall"):
        out = gm.move(p, region, quiet=True)
        assert "hints" not in out
    assert gm.inspect("Cell")["parent"] == region
    assert gm.measure("Cell", "Hall")["ground"] == 20.0  # the spots are as they were, now in the region's frame
    assert not [e for e in nate.perceive()["events"] if e["kind"] in ("moved", "left", "regrouped")]
    assert [e["kind"] for e in gm.history(kinds=["regrouped"])] == ["regrouped", "regrouped"]
    assert nate.perceive()["ambient"].get("heat") == "dry heat"  # the region's air reaches the cell
    with pytest.raises(Rejected) as r:
        gm.move("Cell", region, quiet=True, at=[1, 1, 0])
    assert "keeps the spot" in r.value.reason


def test_tiers_need_no_spot_and_the_map_and_ruler_keep_to_one_frame():
    eng, gm, i, gal, planet, region = grown()
    gm.move("Cell", region, quiet=True)
    gm.move("Hall", region, quiet=True)
    v = gm.verify()
    assert not [p for p in v["page"] if p["id"] in (gal, planet, region)]  # a tier is a container, not a spot
    m = gm.map(under=region)
    assert m["frame"]["units"] == "m" and {r["name"] for r in m["entities"]} >= {"Cell", "Hall"}
    top = gm.map(under=planet)
    assert top["frame"]["units"] == "km"
    assert [r["at"] for r in top["entities"] if r["id"] == region] == [[120.0, 40.0, 0.0]]
    cell = [r for r in gm.map(under=planet, depth=2)["entities"] if r["name"] == "Cell"][0]
    assert cell["frame"] == "The Reach"  # placed in the region's frame, not on the planet's map
    gm.spawn("place", planet, name="The Kiln Basin", state={"tier": "region", "frame": {"units": "m"}})
    yard = gm.spawn("place", "The Kiln Basin", name="Kiln Yard", at=[0, 0, 0])["id"]
    with pytest.raises(Rejected) as r:
        gm.measure("Cell", yard)
    assert "different frames" in r.value.reason
    assert gm.measure("Cell", "Hall")["ground"] == 20.0


def test_a_frame_goes_only_on_a_tier_and_a_place_left_under_the_root_gets_a_hint():
    eng, gm, i, gal, planet, region = grown()
    with pytest.raises(Rejected) as r:
        gm.layout(placements=[{"entity": "Hall", "frame": {"units": "m"}}])
    assert "not a tier" in r.value.reason
    out = gm.spawn("place", "Two Rooms", name="Stray Camp", at=[5, 5, 0])
    assert any("Stray Camp" in h and "region" in h for h in out["hints"])
    assert "hints" not in gm.spawn("place", region, name="Dry Camp", at=[6, 6, 0])
