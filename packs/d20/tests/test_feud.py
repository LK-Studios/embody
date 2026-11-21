"""A feud burns out (d20, asked by the Glass Reach host, 2026-11-21). A blow struck back at someone who struck first
costs no standing: the faction counts who started the fight. Standing lost to blows climbs back a point a world day,
up to -3, just above outlaw. Two sides with no mind used to outlaw each other a blow at a time, for good."""

from packs.d20.tests.test_rules_d20 import outpost, state, strong

DAY = 86400


def standing(gm, who, faction):
    me = gm.inspect(who)["id"]
    fid = gm.inspect(faction)["id"]
    return {e["target"]: e["data"]["value"] for e in gm.world.edges(me, "standing", "out")}.get(fid, 0)


def hits_by(gm, who):
    wid = gm.inspect(who)["id"]
    return len([e for e in gm.world.events(0, kinds=["hit"], limit=5000) if e["payload"].get("by") == wid])


def outlawed(gm):
    return [e for e in gm.world.events(0, kinds=["outlawed"], limit=5000)]


def first_blow(gm):
    # two fighters with no mind, of two sides, and one blow that lands: Carter cannot ward it off, then they are even
    for name, side in [("Raider", "the Rivals"), ("Carter", "the Traders")]:
        gm.spawn("fighter", "The Oasis", name, state={"faction": side, "hp": 60, "max_hp": 60})
    strong(gm, "Raider")
    gm.patch("Carter", {"body": 0, "skills": {}})
    r = gm.act_as("Raider", "attack", "Carter")
    assert "hit" in [e["kind"] for e in r["events"]]
    strong(gm, "Carter")


def test_a_blow_struck_back_costs_no_standing_and_the_first_blow_does():
    eng, gm, you = outpost()
    first_blow(gm)
    assert standing(gm, "Raider", "the Traders") == -2  # the first blow
    for _ in range(20):
        gm.clock(step=6)
    assert hits_by(gm, "Carter") >= 1 and hits_by(gm, "Raider") >= 2
    assert standing(gm, "Carter", "the Rivals") == 0  # every blow of his was defence
    assert standing(gm, "Raider", "the Traders") == -2  # and so were his, once Carter struck back


def test_two_sides_with_no_mind_no_longer_outlaw_each_other():
    eng, gm, you = outpost()
    first_blow(gm)
    for _ in range(60):
        gm.clock(step=6)
    assert hits_by(gm, "Carter") + hits_by(gm, "Raider") >= 4
    assert outlawed(gm) == []
    assert not gm.inspect("the Traders")["state"].get("hostile", {}).get(gm.inspect("Raider")["id"])
    assert not gm.inspect("the Rivals")["state"].get("hostile", {}).get(gm.inspect("Carter")["id"])


def test_standing_lost_to_blows_climbs_back_a_point_a_day_up_to_minus_three():
    eng, gm, you = outpost("Scout")
    gm.patch("Scout", {"water": 10, "hp": 40, "max_hp": 40})
    gm.move("Scout", "The Keep")
    strong(gm, "Scout")
    gm.patch("Warden", {"hp": 60, "max_hp": 60})
    gm.patch("Belt ward", {"on": False})
    start = standing(gm, "Scout", "the Garrison")
    for _ in range(3):  # the Warden has no fighter's tick: he does not strike back, so each blow is a first
        gm.act_as("Scout", "attack", "Warden")
        gm.clock(step=120)
    assert standing(gm, "Scout", "the Garrison") == start - 6
    me = gm.inspect("Scout")["id"]
    garrison = gm.inspect("the Garrison")
    assert garrison["state"]["hostile"].get(me) is True
    rec = garrison["state"]["bruised"][me]
    assert rec["n"] == 6
    # a day on, the Scout's own rest sees it: a point back
    t = gm.summary()["t"]
    gm.patch("the Garrison", {"bruised": {me: dict(rec, at=t - DAY - 1)}})
    gm.clock(step=700)
    assert standing(gm, "Scout", "the Garrison") == start - 5
    assert any(e["payload"].get("why") == "blows forgiven" for e in gm.world.events(0, kinds=["standing"], limit=5000))
    # ten days on, the Garrison's fighters let her be: back to -3 and no further, no longer outlawed
    t = gm.summary()["t"]
    rec = gm.inspect("the Garrison")["state"]["bruised"][me]
    gm.patch("the Garrison", {"bruised": {me: dict(rec, at=t - 10 * DAY)}})
    gm.patch("Scout", {"hp": 40})
    gm.move("Scout", "The Yard")
    before = state(gm, "Scout")["hp"]
    for _ in range(10):
        gm.clock(step=6)
    assert standing(gm, "Scout", "the Garrison") == max(-3, start - 6)
    assert not gm.inspect("the Garrison")["state"]["hostile"].get(me)
    assert state(gm, "Scout")["hp"] >= before
