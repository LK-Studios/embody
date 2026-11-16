"""Far views (src/embody/far.py): what carries `far` lines is seen as far as its size allows, capped by the horizon and
the haze; past half its range it shows its far line, inside it its mid line; a container's line stands for what in it is
small; nothing hidden shows unless the viewer knows the way or the world says it is seen, and then without its name."""

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def skyline():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    root = w.root_id
    tower = gm.spawn("place", root, name="Signal Tower", state={"far": {"far": "a thin grey stalk on the skyline",
                                                                         "mid": "a stone tower, a fire basket on top"}})["id"]
    city = gm.spawn("place", root, name="Varn", state={"far": "a smudge of smoke over a city to the west"})["id"]
    spire = gm.spawn("place", city, name="Varn Spire", state={"far": "a needle of glass"})["id"]
    keep = gm.spawn("place", root, name="Keep of Teeth", state={"hidden": True, "far": {
        "far": "a dark shape on a crag", "seen": True, "called": "a keep on a crag"}})["id"]
    cairn = gm.spawn("place", root, name="Cairn", state={"far": "a heap of stones"})["id"]
    fire = gm.spawn("thing", tower, name="Beacon", state={"hidden": True, "far": "a fire"})["id"]
    gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Cell", "at": [0, 0, 0], "radius": 4}, {"entity": "Hall", "at": [20, 0, 0], "size": [12, 8]},
        {"entity": tower, "at": [0, 5000, 0], "radius": 20, "ceiling": 300},
        {"entity": city, "at": [-40000, 0, 0], "radius": 3000, "ceiling": 100},
        {"entity": spire, "at": [-40000, 0, 0], "radius": 200, "ceiling": 900},
        {"entity": keep, "at": [0, -3000, 0], "radius": 50, "ceiling": 40},
        {"entity": cairn, "at": [0, 20000, 0], "radius": 1},
        {"entity": fire, "at": [0, 5000, 300], "radius": 50}])
    nate = eng.session("nate")
    nate.join("two-rooms", "Prisoner")
    return eng, w, gm, nate


def sight(seat):
    return {(r["name"] or "?"): r for r in seat.perceive(far=True)["in_sight"]}


def test_size_sets_the_range_and_the_band_picks_the_line():
    eng, w, gm, nate = skyline()
    assert "in_sight" not in nate.perceive()  # ordinary perceive stays as it is
    s = sight(nate)
    tower = s["Signal Tower"]
    assert (tower["band"], tower["line"], tower["compass"]) == ("mid", "a stone tower, a fire basket on top", "N")
    assert tower["distance_m"] == 4980 and "hour" in tower["distance"]
    city = s["Varn"]
    assert (city["band"], city["compass"], city["line"]) == ("far", "W", "a smudge of smoke over a city to the west")
    assert "Varn Spire" not in s  # the city's line stands for its spire
    assert "Cairn" not in s and "Beacon" not in s  # too small to see from 20 km; a hidden thing never shows
    keep = s["a keep on a crag"]
    assert keep["id"] is None and keep["line"] == "a dark shape on a crag"  # seen, but nothing revealed
    assert list(s)[0] == "Varn"  # the most prominent first: 6 km of city at 37 km over 300 m of tower at 5 km


def test_merge_size_haze_knowing_the_way_and_indoors():
    eng, w, gm, nate = skyline()
    gm.patch("Varn", {"far": {"far": "a smudge of smoke", "merge_m": 500}})
    gm.patch("Keep of Teeth", {"known_to": [gm.inspect("Prisoner")["id"]]})
    gm.clock(step=3601)  # a new world hour: the cache is fresh
    s = sight(nate)
    assert s["Varn Spire"]["line"] == "a needle of glass"
    assert s["Keep of Teeth"]["id"] is not None
    gm.patch("Cell", {"visibility_m": 1000})  # dust: nothing past a kilometre
    gm.clock(step=3601)
    assert sight(nate) == {}
    gm.patch("Cell", {"visibility_m": None, "indoors": True})
    gm.clock(step=3601)
    b = nate.perceive(far=True)
    assert b["in_sight"] == [] and "indoors" in b["note"]
