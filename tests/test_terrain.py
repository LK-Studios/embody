"""Terrain: a place's ground as a small height grid on its layout, in the frame its own spot is in, so a game's ground
and the world's come from one grid. The layout op checks it, heights read from it between the cells, and reads give a
summary unless they ask for the heights."""

import pytest

from embody import layout as geo
from embody import positions as posn
from embody.world import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def slope(cols=4, rows=3, cell=10.0, origin=(-15.0, -10.0)):
    # rises 1 m a metre east and 2 m a metre north from 0 at the south-west corner
    z = [i * cell + 2 * j * cell for j in range(rows) for i in range(cols)]
    return {"origin": list(origin), "cell_m": cell, "cols": cols, "rows": rows, "z": z, "version": 1, "source": "test"}


def test_a_terrain_grid_is_checked_and_read_between_its_cells():
    t = geo.check_terrain(slope(), {"at": [0, 0, 0], "size": [30, 20]})
    assert geo.height(t, -15, -10) == 0 and geo.height(t, 15, 10) == 30 + 40
    assert geo.height(t, 0, 0) == pytest.approx(15 + 20)  # bilinear between the four cells around it
    assert geo.height(t, 16, 0) is None  # off the grid
    for bad, why in [({**slope(), "cols": 1}, "2 or more"), ({**slope(), "z": [0] * 11}, "12 heights"),
                     ({**slope(), "z": [0] * 11 + [float("nan")]}, "must be a number"),
                     ({**slope(), "cell_m": 0}, "above zero"), ({**slope(), "colour": "red"}, "does not know"),
                     ({**slope(), "cols": 200, "rows": 100, "z": [0] * 20000}, "at most 16384"),
                     (slope(origin=(500, 0)), "outside the place's extent")]:
        with pytest.raises(Rejected, match=why):
            geo.check_terrain(bad, {"at": [0, 0, 0], "size": [30, 20]})
    geo.check_terrain(slope(origin=(-24, -19)), {"at": [0, 0, 0], "size": [30, 20]})  # a cell over the edge is fine


def test_the_layout_op_stores_it_warns_on_a_landmark_off_the_ground_and_reads_give_a_summary():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    r = gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Cell", "at": [-100, 0, 0], "radius": 4},
        {"entity": "Hall", "at": [0, 0, 0], "size": [30, 20],
         "landmarks": {"the pen": {"at": [0, 0, 25], "radius": 2}, "the cairn": {"at": [10, 5, 0], "radius": 1}},
         "terrain": slope()}])
    # the pen sits 10 m below the ground the grid gives it (35): a warning, not a refusal; the cairn 55 m off too
    assert any("under the pen" in x and "off by 10.0" in x for x in r["warnings"])
    assert any("under the cairn" in x for x in r["warnings"])
    assert posn.ground(w, i["Hall"], [0, 0, 0]) == pytest.approx(35)
    assert posn.ground(w, i["Cell"], [-100, 0, 0]) is None  # no terrain there
    m = gm.map()
    hall = next(e for e in m["entities"] if e["name"] == "Hall")
    assert hall["layout"]["terrain"] == {"origin": [-15, -10], "cell_m": 10, "cols": 4, "rows": 3, "version": 1,
                                         "source": "test", "z_min": 0, "z_max": 70}
    full = next(e for e in gm.map(terrain=True)["entities"] if e["name"] == "Hall")
    assert len(full["layout"]["terrain"]["z"]) == 12
    assert "z" not in gm.inspect("Hall")["state"]["layout"]["terrain"]
    with pytest.raises(Rejected, match="outside the place's extent"):
        gm.layout(placements=[{"entity": "Hall", "size": [4, 4]}])  # shrinking the place under its grid
    gm.layout(placements=[{"entity": "Hall", "terrain": None}])
    assert "terrain" not in gm.inspect("Hall")["state"]["layout"]


def hill(eng, w):
    """The Hall as a long strip of ground with a 100 m hill across its middle, x -20 to 20; a tower 5 km east."""
    gm = owner(eng)
    z = [100.0 if -20 <= -200 + 10 * i <= 20 else 0.0 for j in range(3) for i in range(41)]
    tower = gm.spawn("place", w.root_id, name="Signal Tower", state={"far": "a thin grey stalk"})["id"]
    gm.spawn("place", "Hall", name="Cellar")
    gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Cell", "at": [-1000, 0, 0], "radius": 4},
        {"entity": "Hall", "at": [0, 0, 0], "size": [400, 40],
         "terrain": {"origin": [-200, -10], "cell_m": 10, "cols": 41, "rows": 3, "z": z}},
        {"entity": "Cellar", "at": [0, 0, -25], "radius": 5},
        {"entity": "Guard", "at": [-150, 0]},
        {"entity": tower, "at": [5000, 0, 0], "radius": 20, "ceiling": 300}])
    return gm


def test_bodies_stand_on_the_ground_and_a_place_inside_keeps_its_own():
    eng, w, i = engine_with_two_rooms()
    gm = hill(eng, w)
    assert gm.inspect("Guard")["state"]["layout"]["at"] == [-150, 0, 0]
    gm.layout(placements=[{"entity": "Guard", "at": [0, 0]}])
    assert gm.inspect("Guard")["state"]["layout"]["at"] == [0, 0, 100]  # [x, y]: the ground's height
    gm.layout(placements=[{"entity": "Guard", "at": [-30, 0, 7]}])
    assert gm.inspect("Guard")["state"]["layout"]["at"] == [-30, 0, 7]  # an author's own z stands
    assert gm.inspect("Cellar")["state"]["layout"]["at"] == [0, 0, -25]  # a place under the hill keeps its z
    nate = eng.session("nate")
    nate.join("two-rooms", "Guard")
    gm.patch("Guard", {"speed_mps": 10})
    r = nate.step([-21, 0])
    assert r["at"][2] == pytest.approx(90, abs=0.01)  # a step goes up the slope with the ground (0 at -30, 100 at -20)
    r = nate.step([-15, 0])
    assert r["at"] == [-15, 0, 100]


def test_the_ground_hides_what_lies_behind_a_hill_and_a_hilltop_sees_over_it():
    eng, w, i = engine_with_two_rooms()
    gm = hill(eng, w)
    nate = eng.session("nate")
    nate.join("two-rooms", "Guard")

    def sees_tower(seat):
        return any(r["name"] == "Signal Tower" for r in seat.perceive(far=True)["in_sight"])

    assert not sees_tower(nate)  # below the hill, 130 m short of it
    gm.layout(placements=[{"entity": "Guard", "at": [0, 0]}])
    assert sees_tower(nate)  # on its top: the eye is 101.7 m up
    sam = eng.session("sam")
    sam.join("two-rooms", "Prisoner")  # in the Cell, a kilometre west: the Hall's hill is in the way too
    assert not sees_tower(sam)
