"""A herd that lives where it is watched: beasts nobody holds amble about their place now and then (near their herd,
inside the place, out of anything solid, facing the way they go), only where someone holds a body or the place says
`amble`; beasts that walk in spread out; a held beast moves only as its holder steps it; and an upgrade gives beasts
already in a world the tick their schema gained since they were born."""

from embody.workspace import standing_ticks
from packs.beasts.tests.test_beasts import DAY, wild  # noqa: F401  (the fixture)


def ridge(gm, n=3):
    gm.world.set_pace({"beast_amble": 30})
    gm.layout(frame={"units": "m"}, placements=[{"entity": "Ridge", "at": [0, 0, 0], "size": [40, 30]}])
    rock = gm.spawn("thing", "Ridge", "Boulder")["id"]
    gm.layout(placements=[{"entity": rock, "at": [6, 0, 0], "radius": 1.5, "solid": True}])
    return [gm.spawn("beast", "Ridge", f"Goat {k}", state={"species": "goat", "stage": "adult", "fed": 3,
                                                            "sex": "f", "home": "Ridge"})["id"] for k in range(n)]


def run(gm, secs):
    # thirty seconds at a time, as a running clock delivers them: one long step fires a periodic tick once
    for _ in range(int(secs // 30)):
        gm.clock(step=30)


def at(gm, eid):
    return (gm.world.need(eid)["state"].get("layout") or {}).get("at")


def steps(gm, since, eid=None):
    return [e for e in gm.world.store.query("event", "world_id=? AND seq>? AND kind='stepped'", (gm.world.id, since),
                                            order="seq") if eid is None or e["actor_id"] == eid]


def inside(p):
    return -20 <= p[0] <= 20 and -15 <= p[1] <= 15


def test_goats_spread_out_then_amble_only_while_someone_is_there(wild):
    eng, gm = wild
    goats = ridge(gm)
    gm.clock(step=31)
    spots = [at(gm, g) for g in goats]
    assert all(spots) and all(inside(p) for p in spots)
    assert all(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 >= 0.5 for i, a in enumerate(spots) for b in spots[i + 1:])
    seq = gm.world.store.next_seq(gm.world.id) - 1
    run(gm, 600)
    assert [at(gm, g) for g in goats] == spots and not steps(gm, seq)  # nobody here: nothing moves, nothing is written
    gm.move("Ada", "Ridge")
    ada = eng.session("ada")
    ada.join("wild", "Ada")
    seq = gm.world.store.next_seq(gm.world.id) - 1
    run(gm, 900)
    moved = steps(gm, seq)
    assert len({e["actor_id"] for e in moved}) >= 2 and len(moved) <= 3 * 30
    for g in goats:
        mine = steps(gm, seq, g)
        assert all(b["t"] - a["t"] >= 30 for a, b in zip(mine, mine[1:]))  # never more often than its tick
        assert all(inside(e["payload"]["at"]) and "heading" in e["payload"] for e in mine)
    assert all(not (4.5 < at(gm, g)[0] < 7.5 and -1.5 < at(gm, g)[1] < 1.5) for g in goats)  # out of the boulder
    xs = [at(gm, g) for g in goats]
    cx, cy = sum(p[0] for p in xs) / 3, sum(p[1] for p in xs) / 3
    assert all(((p[0] - cx) ** 2 + (p[1] - cy) ** 2) ** 0.5 < 14 for p in xs)  # the herd keeps together
    assert any(e["kind"] == "stepped" for e in ada.wait(timeout=0, since=seq)["events"])


def test_a_held_goat_waits_for_its_holder_and_a_watched_place_ambles_alone(wild):
    eng, gm = wild
    goats = ridge(gm)
    gm.clock(step=31)
    sam = eng.session("sam")
    sam.join("wild", "Goat 0")
    held = at(gm, goats[0])
    seq = gm.world.store.next_seq(gm.world.id) - 1
    run(gm, 900)
    assert at(gm, goats[0]) == held and not steps(gm, seq, goats[0])
    assert steps(gm, seq, goats[1]) or steps(gm, seq, goats[2])  # sam is here: the rest of the herd moves
    sam.leave()
    gm.patch("Ridge", {"amble": True})  # a game's client watches this place: it lives with nobody in it
    seq = gm.world.store.next_seq(gm.world.id) - 1
    run(gm, 900)
    assert steps(gm, seq, goats[0])
    gm.patch(goats[1], {"amble": False})  # a beast (or its species) that keeps still
    seq = gm.world.store.next_seq(gm.world.id) - 1
    run(gm, 900)
    assert not steps(gm, seq, goats[1]) and steps(gm, seq, goats[2])


def test_an_upgrade_gives_old_beasts_the_tick_their_schema_gained(wild):
    eng, gm = wild
    goats = ridge(gm, n=2)
    w = gm.world
    w.store.execute("DELETE FROM scheduled WHERE world_id=? AND entity_id=? AND payload LIKE '%beast_amble%'",
                    (w.id, goats[0]))
    assert standing_ticks(w) == 1 and standing_ticks(w) == 0
    tick = [i for i in w.pending() if i["entity_id"] == goats[0] and i["payload"].get("script") == "beast_amble"]
    assert len(tick) == 1 and tick[0]["every"] == 30.0  # the world's pace, not the schema's beat
