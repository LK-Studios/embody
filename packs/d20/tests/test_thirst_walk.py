"""A thirst walk keeps clear of danger (d20, asked by the Glass Reach host, 2026-11-21). Ruhl's seat, held by a mind on
a watcher, went idle; its idle care walked the body off for water and through the people who had outlawed it. A held
seat now drinks what is in reach and never walks, and a body nobody holds walks around a side that outlawed it."""

from packs.d20.tests.test_rules_d20 import outpost, state


def where(gm, name):
    return gm.world.get(gm.inspect(name)["parent"])["name"]


def test_a_held_seat_gone_idle_drinks_what_is_in_reach_and_never_walks():
    eng, gm, you = outpost()
    gm.spawn("person", "The Flats", "Walker", state={"faction": "the Garrison", "playable": True, "water": 2,
                                                     "max_water": 10})
    gm.world.set_meta({"idle_after": 50})
    eng.session("mind").join("outpost", "Walker")
    for _ in range(4):
        gm.clock(step=60)
    assert gm.world.idle(gm.inspect("Walker")["id"])
    assert where(gm, "Walker") == "The Flats" and not state(gm, "Walker").get("post")  # thirsty, and it stays put
    dry = state(gm, "Walker")["water"]
    gm.spawn("waterskin", "Walker", "Walker's skin", state={"left": 2})
    gm.clock(step=60)
    assert state(gm, "Walker")["water"] == min(10, dry + 4) and state(gm, "Walker's skin")["left"] == 1  # a skin in hand it drinks
    assert where(gm, "Walker") == "The Flats"


def test_a_thirst_walk_goes_around_a_side_that_outlawed_the_body_or_waits():
    eng, gm, you = outpost()
    wid = gm.spawn("person", "The Flats", "Walker", state={"faction": "the Garrison", "water": 2,
                                                           "max_water": 10, "hp": 40, "max_hp": 40})["id"]
    gm.spawn("fighter", "The Road", "Carter", state={"faction": "the Traders"})
    gm.patch("the Traders", {"hostile": {wid: True}})
    for _ in range(3):
        gm.clock(step=60)
    assert where(gm, "Walker") == "The Flats"  # every way to water runs through the Road, where Carter stands: it waits
    gm.move("Carter", "The Oasis")
    trail = []
    for _ in range(8):
        gm.clock(step=60)
        trail.append(where(gm, "Walker"))
    assert trail[:3] == ["The Road", "The Yard", "The Keep"], trail  # the long way round, to the cistern
    assert "The Oasis" not in trail and state(gm, "Walker")["post"] == gm.inspect("The Flats")["id"], trail
    gm.move("Walker", "The Road")
    gm.patch("Walker", {"water": 2, "post": None})
    gm.clock(step=60)
    assert where(gm, "Walker") == "The Yard"  # Carter stands at the seep: around him
    gm.move("Walker", "The Road")
    gm.patch("Carter", {"down": True})
    gm.clock(step=60)
    assert where(gm, "Walker") == "The Oasis"  # a foe who is down guards nothing: the near way is open
