"""packs/burial at a small hamlet with a graveyard: the dead turn foul and then to bones by world time, a carcass
stops being meat, a sweep finds the dead no rule heard die, bury only on a burial ground (words, a marker), a held
dead seat's leave or the world's wait, inscribe, adorn, exhume at a cost in standing, and an undertaker with no
seat burying through the same verb."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
DAY = 86400
DIG = 901

BUILD = '''
from packs.burial.pack import install_rules

WORLD = {"id": "hamlet", "name": "Hamlet", "seed": 7, "description": "A lane and a graveyard.",
         "requires": ["village", "d20", "burial"]}

def define(s):
    s.define_schema("person", extends="combatant",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
                             "take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"},
                             "read": {"script": "read", "doc": "Read it", "targets": "thing"}})

def populate(s):
    root = s.summary()["root"]
    lane = s.spawn("place", root, "Lane")["id"]
    yard = s.spawn("place", root, "Graveyard", state={"burial_ground": True})["id"]
    s.connect(lane, yard)
    s.spawn("faction", root, "Hamlet folk")
    ada = s.spawn("person", yard, "Ada", state={"water": 10})["id"]
    s.spawn("thing", ada, "Cairn stone", state={"portable": True})
    s.spawn("person", yard, "Bel", state={"down": True, "faction": "Hamlet folk",
                                          "description": "A thin man in a grey coat."})
    s.spawn("person", yard, "Cara", state={"water": 10})
    s.spawn("person", yard, "Digger", state={"water": 10})
    install_rules(s, root)
    s.clock(run=False)
'''


@pytest.fixture
def hamlet(tmp_path):
    for p in ("village", "d20", "burial"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "hamlet").mkdir(parents=True)
    (tmp_path / "worlds" / "hamlet" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "hamlet")
    # days at a time: the bodies' minute ticks (thirst above all) would kill everyone or take the test all day
    gm.world.set_pace({"thirst": 100 * DAY, "quench": 100 * DAY, "mend": 100 * DAY, "fighter_tick": 100 * DAY})
    ada, cara = eng.session("ada"), eng.session("cara")
    ada.join("hamlet", "Ada")
    cara.join("hamlet", "Cara")
    return eng, gm, ada, cara


def st(gm, name):
    return gm.world.need(gm._resolve(name))["state"]


def kinds(gm, kind):
    return [e for e in gm.world.events(0, kinds=[kind], limit=5000)]


def kill_bel(ada):
    ada.act("kill", "Bel")


def test_the_dead_turn_foul_then_to_bones_by_world_time(hamlet):
    eng, gm, ada, cara = hamlet
    kill_bel(ada)
    bel = st(gm, "Bel")
    assert bel["decay"] == "fresh" and bel["died_at"] is not None
    gm.clock(step=DAY + 1)
    bel = st(gm, "Bel")
    assert bel["decay"] == "foul"
    assert bel["description"].startswith("A thin man in a grey coat.") and "flies" in bel["description"]
    assert ada.inspect("Bel")["condition"] == "dead" and ada.inspect("Bel")["decay"] == "foul"
    gm.clock(step=6 * DAY)
    bel = st(gm, "Bel")
    assert bel["decay"] == "bones" and bel["description"].startswith("Bones")
    assert bel["description_alive"] == "A thin man in a grey coat."
    assert [e["payload"]["stage"] for e in kinds(gm, "decayed")] == ["foul", "bones"]


def test_the_world_sets_the_stage_lengths_and_a_carcass_stops_being_meat(hamlet):
    eng, gm, ada, cara = hamlet
    gm.patch(gm.world.root_id, {"burial": {"decay_beast": {"foul": 3600, "bones": 7200},
                                           "notes": {"bones_beast": "A ribcage in the grass."}}})
    gm.spawn("creature", "Graveyard", "Dead goat", state={"beast": True, "dead": True, "food": ["meat", "carrion"],
                                                          "meals": 4})
    gm.clock(step=61)  # the sweep finds a body no rule heard die
    assert st(gm, "Dead goat")["decay"] == "fresh"
    gm.clock(step=3601)
    goat = st(gm, "Dead goat")
    assert goat["decay"] == "foul" and goat["food"] == ["carrion"]
    gm.clock(step=3601)
    goat = st(gm, "Dead goat")
    assert goat["decay"] == "bones" and "food" not in goat and goat["meals"] == 0
    assert goat["description"] == "A ribcage in the grass."


def test_bury_only_on_a_burial_ground_with_words_and_a_marker(hamlet):
    eng, gm, ada, cara = hamlet
    kill_bel(ada)
    gm.move("Bel", "Lane")
    gm.move("Ada", "Lane")
    with pytest.raises(Rejected) as r:
        ada.act("bury", "Bel")
    assert "burial_ground" in r.value.reason
    gm.move("Bel", "Graveyard")
    gm.move("Ada", "Graveyard")
    bel_id = gm._resolve("Bel")
    with pytest.raises(Rejected) as r:
        ada.act("bury", "Bel", {"words": f"{bel_id} rests"})
    assert "ids and tool calls" in r.value.reason
    with pytest.raises(Rejected):
        ada.act("bury", "Cara")  # alive
    ada.act("bury", "Bel", {"words": "He kept the lane swept.", "marker": "Cairn stone"})
    assert st(gm, "Ada")["water"] == 8
    gm.clock(step=DIG)
    grave = [g for g in gm.find(type="grave")][0]
    g = st(gm, grave["id"])
    assert (g["lies"], g["buried_by"], g["words"]) == ("Bel", "Ada", "He kept the lane swept.")
    assert grave["name"] == "Grave of Bel"
    bel = gm.world.need(bel_id)
    assert bel["parent_id"] == grave["id"] and bel["state"]["hidden"] and bel["state"]["buried_in"] == grave["id"]
    stone = st(gm, "Cairn stone")
    assert stone["attached"] and stone["portable"] is False and stone["marker_of"] == grave["id"]
    assert "Cairn stone" in g["description"]
    assert [e["payload"]["body"] for e in kinds(gm, "buried")] == [bel_id]
    assert len(kinds(gm, "grave_marked")) == 1
    seen = ada.perceive()
    assert bel_id not in str(seen["present"]) and bel_id not in [a.get("target") for a in seen.get("affordances") or []]
    with pytest.raises(Rejected):
        ada.act("bury", bel_id)


def test_a_held_dead_seat_gives_its_leave_or_the_world_waits(hamlet):
    eng, gm, ada, cara = hamlet
    bel = eng.session("bel")
    bel.join("hamlet", "Bel")
    kill_bel(ada)
    with pytest.raises(Rejected) as r:
        ada.act("bury", "Bel")
    assert "let_bury" in r.value.reason
    with pytest.raises(Rejected) as r:
        bel.act("take", "Cairn stone")
    assert r.value.reason == "you are dead" and "let_bury" in r.value.hint
    bel.act("let_bury")
    assert kinds(gm, "left_to_bury")
    ada.act("bury", "Bel")
    gm.clock(step=DIG)
    assert gm.find(type="grave")


def test_the_world_wait_lets_a_held_body_be_buried(hamlet):
    eng, gm, ada, cara = hamlet
    eng.session("bel").join("hamlet", "Bel")
    gm.patch(gm.world.root_id, {"burial": {"seat_wait": 600}})
    kill_bel(ada)
    with pytest.raises(Rejected):
        ada.act("bury", "Bel")
    gm.clock(step=601)
    ada.act("bury", "Bel")


def buried(gm, ada):
    kill_bel(ada)
    ada.act("bury", "Bel")
    gm.clock(step=DIG)
    return gm.find(type="grave")[0]["id"]


def test_inscribe_and_adorn(hamlet):
    eng, gm, ada, cara = hamlet
    gid = buried(gm, ada)
    ada.act("inscribe", gid, {"text": "Bel, who swept the lane"})
    gm.clock(step=61)
    assert 'Cut into its headboard: "Bel, who swept the lane"' in st(gm, gid)["description"]
    assert ada.act("read", gid)
    with pytest.raises(Rejected) as r:
        cara.act("inscribe", gid, {"text": "Nobody"})
    assert "only whoever cut it" in r.value.reason
    with pytest.raises(Rejected):
        cara.act("inscribe", gid, {"text": "x" * 121})
    ada.act("mark", gid, {"item": "Cairn stone"})
    gm.clock(step=31)
    ada.act("inscribe", gid, {"text": "Bel of the lane"})
    gm.clock(step=61)
    assert st(gm, "Cairn stone")["text"] == "Bel of the lane"
    assert 'Cut into it: "Bel of the lane"' in st(gm, gid)["description"]
    gm.patch(gm.world.root_id, {"burial": {"adorn_max": 2}})
    cara.act("adorn", gid, {"text": "a ring of white stones"})
    gm.clock(step=21)
    ada.act("adorn", gid, {"text": "a strip of red cloth"})
    gm.clock(step=21)
    with pytest.raises(Rejected) as r:
        cara.act("adorn", gid, {"text": "a third thing"})
    assert "all it can hold" in r.value.reason
    g = st(gm, gid)
    assert "A ring of white stones. A strip of red cloth." in g["description"]
    assert [a["by"] for a in g["adornments"]] == ["Cara", "Ada"] and all("t" in a for a in g["adornments"])
    assert len(kinds(gm, "inscribed")) == 2 and len(kinds(gm, "adorned")) == 2


def test_exhume_costs_standing_with_the_dead_ones_people(hamlet):
    eng, gm, ada, cara = hamlet
    gm.patch(gm.world.root_id, {"burial": {"exhume_crime": True}})
    gid = buried(gm, ada)
    ada.act("mark", gid, {"item": "Cairn stone"})
    gm.clock(step=31)
    cara.act("exhume", gid)
    gm.clock(step=DIG)
    assert not gm.find(type="grave")
    bel = gm.world.need(gm._resolve("Bel"))
    assert gm.world.need(bel["parent_id"])["name"] == "Graveyard" and not bel["state"]["hidden"]
    assert "buried_in" not in bel["state"]
    stone = st(gm, "Cairn stone")
    assert stone["portable"] is True and "attached" not in stone
    ex = kinds(gm, "exhumed")
    assert len(ex) == 1 and ex[0]["payload"]["crime"] is True
    folk = [f for f in gm.find(type="faction") if f["name"] == "Hamlet folk"][0]["id"]
    edge = [e for e in gm.world.edges(gm._resolve("Cara"), "standing", "out") if e["target"] == folk][0]
    assert edge["data"]["value"] == -2


def test_an_undertaker_with_no_seat_buries_through_the_same_verb(hamlet):
    eng, gm, ada, cara = hamlet
    kill_bel(ada)
    w = gm.world
    w.act(gm._resolve("Digger"), "bury", gm._resolve("Bel"), {"words": "Rest."})
    gm.clock(step=DIG)
    assert st(gm, gm.find(type="grave")[0]["id"])["buried_by"] == "Digger"
