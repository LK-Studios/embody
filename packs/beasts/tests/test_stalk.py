"""A hunt with a warning window, in a world that names strike kinds: at dusk a hungry pack comes to its prey and waits
(stalks), at the night it falls on it; herders standing with the herd may turn it back, anyone there may drive it off,
some nights it only prowls, and whatever never struck goes home at dawn. Out of its den it wears its species' far line."""

from packs.beasts.pack import install_rules
from packs.beasts.tests.test_beasts import DAY, goat, hunting_ground, jackals, st, wild  # noqa: F401  (the fixture)

PACK = ["Jackal 0", "Jackal 1", "Jackal 2"]
FAR = {"far": "low shapes loping through the dust", "size_m": 40, "stands_out": True}


def night_world(gm, herd=None):
    hunting_ground(gm)
    root = gm.world.root_id
    install_rules(gm, root, night="dusk", strike="night")
    gm.patch("jackal", {"far_out": FAR})
    goats = [goat(gm, f"Goat {i}", sex, age=12 + i * 5) for i, sex in enumerate(["m", "f", "f", "f"])]
    goats.append(goat(gm, "Kid", "f", age=1, stage="young"))
    if herd:
        for g in goats:
            gm.patch(g, {"herd": herd})
    jackals(gm, fed=0)
    return root


def at(gm, kind, since=0):
    return [e for e in gm.world.store.query("event", "world_id=? AND kind=? AND seq>?", (gm.world.id, kind, since),
                                            order="seq")]


def where(gm, name):
    return gm.world.get(gm.inspect(name)["parent"])["name"]


def dusk_then_night(gm, root):
    gm.schedule(100, "dusk", entity=root)
    gm.schedule(200, "night", entity=root)
    gm.clock(step=150)


def test_a_pack_stalks_at_dusk_and_strikes_at_night(wild):
    eng, gm = wild
    root = night_world(gm)
    dusk_then_night(gm, root)
    stalks = at(gm, "beast_stalks")
    assert len(stalks) == 1 and not at(gm, "beast_hunts") and not at(gm, "killed")  # seen coming, nothing struck yet
    prey = stalks[0]["payload"]["prey"]
    assert all(where(gm, j) == "Ridge" and st(gm, j)["stalking"] == prey for j in PACK)
    assert all(st(gm, j)["far"] == FAR for j in PACK)  # out of the den: seen from afar
    gm.clock(step=100)
    hunts = at(gm, "beast_hunts")
    assert len(hunts) == 1 and hunts[0]["payload"]["prey"] == prey
    assert at(gm, "killed") or at(gm, "beast_fled") or at(gm, "beast_hunt_failed")
    assert all(st(gm, j).get("stalking") is None for j in PACK)


def test_herders_with_the_herd_turn_the_pack_back(wild):
    eng, gm = wild
    root = night_world(gm, herd="the Keth")
    gm.spawn("person", "Ridge", "Tam", state={"faction": "the Keth", "wits": 3, "skills": {"survival": 20}})
    gm.spawn("person", "Ridge", "Stranger", state={"faction": "the Salt", "wits": 0, "skills": {}})
    dusk_then_night(gm, root)
    gm.clock(step=100)
    back = at(gm, "beast_turned_back")
    assert len(back) == 1 and back[0]["payload"]["by"] == gm.inspect("Tam")["id"] and not at(gm, "killed")
    assert all(where(gm, j) == "Dunes" and st(gm, j).get("far") is None for j in PACK)  # home, and out of sight


def test_anyone_there_may_drive_a_stalking_pack_off_and_their_people_help(wild):
    eng, gm = wild
    root = night_world(gm)
    gm.move("Ada", "Ridge")
    gm.patch("Ada", {"faction": "the Keth", "skills": {"survival": 20}})
    gm.spawn("person", "Ridge", "Tam", state={"faction": "the Keth"})
    dusk_then_night(gm, root)
    gm.act_as("Ada", "drive_off", "Jackal 0")
    off = at(gm, "beast_driven_off")
    assert len(off) == 1 and off[0]["payload"]["dc"] == 10 + 2 * 3 - 2  # three of the pack, one of her own by her
    assert all(where(gm, j) == "Dunes" and st(gm, j).get("stalking") is None for j in PACK)
    gm.clock(step=100)
    assert not at(gm, "beast_hunts")  # driven off: no strike tonight


def test_a_bad_shout_lets_the_pack_stand_and_one_comes_at_you(wild):
    eng, gm = wild
    root = night_world(gm)
    gm.move("Ada", "Ridge")
    gm.patch("Ada", {"wits": 0, "will": 0, "skills": {"survival": -20}})
    dusk_then_night(gm, root)
    seq = gm.world.store.next_seq(gm.world.id) - 1
    gm.act_as("Ada", "drive_off", "Jackal 0")
    assert at(gm, "beast_stood_ground", seq) and not at(gm, "beast_driven_off")
    assert any(e["payload"]["by"] == gm.inspect("Jackal 0")["id"] for e in at(gm, "hit", seq) + at(gm, "missed", seq))
    assert all(st(gm, j)["stalking"] for j in PACK)


def test_some_nights_a_pack_only_prowls_and_goes_home_at_dawn(wild):
    eng, gm = wild
    root = night_world(gm)
    gm.patch("jackal", {"prowls": 1.0})
    dusk_then_night(gm, root)
    prowls = at(gm, "beast_prowls")
    assert len(prowls) == 1 and not at(gm, "beast_stalks")
    assert all(where(gm, j) == "Ridge" and st(gm, j)["far"] == FAR for j in PACK)
    gm.clock(step=100)
    assert not at(gm, "beast_hunts")  # a prowl strikes nothing
    gm.clock(step=DAY)
    assert all(where(gm, j) == "Dunes" and not st(gm, j).get("prowling") and st(gm, j).get("far") is None for j in PACK)


def test_a_pack_calls_the_strike_off_when_its_prey_is_out_of_reach(wild):
    eng, gm = wild
    root = night_world(gm)
    dusk_then_night(gm, root)
    for g in [e for e in gm.world.children(gm.inspect("Ridge")["id"]) if e["state"].get("species") == "goat"]:
        gm.move(g["id"], "Yard")  # the herd is brought in to the yard, out of the pack's reach
    gm.clock(step=100)
    off = at(gm, "beast_called_off")
    assert len(off) == 1 and off[0]["payload"]["why"] == "no prey" and not at(gm, "beast_hunts")
