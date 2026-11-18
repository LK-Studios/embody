"""Rest heals a beast as it heals people, with no water to pay: a point a beat at the world's pace, the wound closing
above half, half the pace hungry, double asleep, none while it fights or hunts, up at 2 from a wound's down, none for
a species that says so, and an upgrade gives beasts already in a world the tick."""

from embody.workspace import standing_ticks
from packs.beasts.tests.test_beasts import DAY, beast, st, wild  # noqa: F401  (the fixture)

BEAT = 600


def rest(gm, beats=1):
    for _ in range(beats):
        gm.clock(step=BEAT)


def hurt(gm, name, **state):
    s = {"hp": 1, "max_hp": 6, "wounded": True}
    s.update(state)
    return beast(gm, "Brake", name, **s)


def mended(gm, eid):
    return [e for e in gm.world.events(0, kinds=["mended"], limit=1000) if e["target_id"] == eid]


def test_a_hurt_beast_mends_a_point_a_beat_and_its_wound_closes_past_half(wild):
    eng, gm = wild
    gm.world.set_pace({"beast_rest": BEAT})
    b = hurt(gm, "Old sow")
    rest(gm, 2)
    assert st(gm, b)["hp"] == 3 and st(gm, b)["wounded"] is True
    assert mended(gm, b)[-1]["payload"]["by"] == "rest" and "water" not in mended(gm, b)[-1]["payload"]
    rest(gm)
    assert st(gm, b)["hp"] == 4 and st(gm, b)["wounded"] is False
    rest(gm, 5)
    assert st(gm, b)["hp"] == 6 and len(mended(gm, b)) == 5  # full: no more beats written
    assert st(gm, b).get("water") is None  # no water asked of it


def test_hungry_half_asleep_double_and_none_in_a_fight_or_on_a_hunt(wild):
    eng, gm = wild
    gm.world.set_pace({"beast_rest": BEAT})
    lean = hurt(gm, "Lean boar", hungry=True)
    sleeper = hurt(gm, "Sleeping sow", asleep=True)
    fighter = hurt(gm, "Angry boar", attacked_by=gm._resolve("Ada"))
    hunter = hurt(gm, "Stalker", stalking=gm._resolve("Ada"))
    rest(gm, 2)
    assert st(gm, lean)["hp"] == 2 and st(gm, sleeper)["hp"] == 5
    assert st(gm, fighter)["hp"] == 1 and st(gm, hunter)["hp"] == 1


def test_a_beast_a_wound_put_down_gets_up_at_two_and_a_species_may_not_mend(wild):
    eng, gm = wild
    gm.world.set_pace({"beast_rest": BEAT})
    down = hurt(gm, "Felled sow", hp=0, down=True, downed_by=gm._resolve("Ada"))
    rest(gm)
    assert st(gm, down)["down"] is True
    rest(gm)
    assert st(gm, down)["hp"] == 2 and st(gm, down)["down"] is False
    assert [e for e in gm.world.events(0, kinds=["rose"], limit=100) if e["target_id"] == down][0]["payload"]["by"] == "rest"
    gm.patch("goat", {"rest_mends": 0})
    g = gm.spawn("beast", "Ridge", "Stone goat", state={"species": "goat", "stage": "adult", "hp": 1, "max_hp": 4})["id"]
    rest(gm, 3)
    assert st(gm, g)["hp"] == 1


def test_an_upgrade_gives_old_beasts_the_rest_tick(wild):
    eng, gm = wild
    b = hurt(gm, "Old boar")
    w = gm.world
    w.store.execute("DELETE FROM scheduled WHERE world_id=? AND entity_id=? AND payload LIKE '%beast_rest%'", (w.id, b))
    assert standing_ticks(w) == 1 and standing_ticks(w) == 0
    assert [i for i in w.pending() if i["entity_id"] == b and i["payload"].get("script") == "beast_rest"]
