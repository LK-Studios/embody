"""Scars: with the root's looks_rules {scar_damage} set, a blow dealing at least that much leaves a permanent near mark
on a region the world's dice pick (src/embody/looks.py). Off by default."""

from packs.d20.tests.test_rules_d20 import reach, state


def blow(gm, you, foe):
    me = gm.inspect("Reeve Ansel Varrick")["id"]
    gm.patch(me, {"body": 40})  # d20 + 40 beats any d20 + wits; his blade deals 2
    gm.spawn("person", gm.world.need(me)["parent_id"], foe,
             state={"hp": 30, "max_hp": 30, "looks": {"regions": ["face", "arms"]}})
    return you.act("attack", foe)


def test_no_scar_unless_the_world_asks_for_one():
    eng, gm, you = reach()
    r = blow(gm, you, "Brawler")
    assert "marked" not in [e["kind"] for e in r["events"]]
    assert not (state(gm, "Brawler")["looks"].get("marks"))


def test_a_hard_blow_leaves_a_scar_on_one_of_the_bodys_regions():
    eng, gm, you = reach()
    gm.patch(gm.world.root_id, {"looks_rules": {"scar_damage": 2}})
    r = blow(gm, you, "Brawler")
    ev = [e["payload"] for e in r["events"] if e["kind"] == "marked"]
    assert len(ev) == 1 and ev[0]["where"] in ("face", "arms")
    assert (ev[0]["kind"], ev[0]["band"]) == ("permanent", "near") and ev[0]["what"] == "a fresh scar from Reeve's blade"
    marks = state(gm, "Brawler")["looks"]["marks"]
    assert list(marks) == ["m1"]
    gm.patch(gm.world.root_id, {"looks_rules": {"scar_damage": 3}})  # a 2-point blow is under it now
    r = you.act("attack", "Brawler")
    assert "marked" not in [e["kind"] for e in r["events"]]
