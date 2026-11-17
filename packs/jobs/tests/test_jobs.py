"""packs/jobs at a small herders' camp: a promise job a giver carries and offers (the gate on standing with his
people, explained), done only by the taker's own kill of the right beast at night, paid in things, standing and a
deed, counted toward the herd's safety, closed after and opened again by a world rule; a posting anyone here may take,
its slots, a delivery job done by handing a thing to the giver, a job that fails when its days run out, and one
dropped."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())
DAY = 86400

BUILD = '''
from packs.jobs.pack import install_rules

WORLD = {"id": "camp", "name": "Camp", "seed": 7, "description": "A herders' camp and its slope.",
         "requires": ["village", "d20", "jobs"]}

def define(s):
    s.define_schema("person", extends="combatant",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
                             "take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"},
                             "give": {"script": "give", "doc": "Hand over", "targets": "creature", "scope": "here",
                                      "params": {"item": "what", "count": "how many"}}})

def populate(s):
    root = s.summary()["root"]
    camp = s.spawn("place", root, "Fold")["id"]
    slope = s.spawn("place", root, "Slope")["id"]
    s.connect(camp, slope)
    s.spawn("faction", root, "Herders")
    s.spawn("thing", root, "Herd", state={"hidden": True, "safety": 0})
    nico = s.spawn("person", camp, "Nico", state={"faction": "Herders", "water": 10})["id"]
    s.spawn("thing", nico, "Flatbread", state={"portable": True, "kind": "flatbread", "count": 5})
    s.spawn("job", nico, "Jackal hunt", state={
        "hidden": True, "giver": "Nico", "terms": "Kill a jackal on the slope at night; two flatbreads.",
        "gate": {"standing": {"Herders": 1}},
        "done": {"kind": "killed", "species": "jackal", "at": "Slope"},
        "window": {"night": True},
        "pay": {"items": [{"kind": "flatbread", "count": 2}], "standing": 1, "deed": {"skill": "survival", "amount": 1}},
        "repeat": "reopen", "toward": {"entity": "Herd", "key": "safety"}})
    s.spawn("job", camp, "Water run", state={
        "giver": "Nico", "terms": "Bring Nico a water skin.", "slots": 2,
        "done": {"kind": "given", "item": "water skin"}, "pay": {"standing": 1}, "repeat": "always"})
    s.spawn("job", camp, "Count the herd", state={
        "giver": "Nico", "terms": "Walk the slope within a day.", "done": {"kind": "arrived", "at": "Slope"},
        "window": {"days": 1}})
    s.spawn("job", slope, "Drive the pack", state={
        "giver": "Nico", "terms": "Drive the jackals off the slope.", "repeat": "always",
        "done": {"kind": ["beast_driven_off", "beast_turned_back"], "species": "jackal"}})
    s.spawn("person", camp, "Ada", state={"water": 10})
    s.spawn("person", camp, "Cara", state={"water": 10})
    s.spawn("thing", s.world.find(name="Cara")[0]["id"], "Water skin", state={"portable": True})
    for n in ("Jackal one", "Jackal two"):
        s.spawn("person", slope, n, state={"down": True, "species": "jackal"})
    install_rules(s, root)
    s.clock(run=False)
'''


@pytest.fixture
def camp(tmp_path):
    for p in ("village", "d20", "jobs"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "camp").mkdir(parents=True)
    (tmp_path / "worlds" / "camp" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "camp")
    gm.world.set_pace({"thirst": 100 * DAY, "quench": 100 * DAY, "mend": 100 * DAY, "fighter_tick": 100 * DAY})
    ada, cara, nico = eng.session("ada"), eng.session("cara"), eng.session("nico")
    ada.join("camp", "Ada")
    cara.join("camp", "Cara")
    nico.join("camp", "Nico")
    return eng, gm, ada, cara, nico


def st(gm, name):
    return gm.world.need(gm._resolve(name))["state"]


def kinds(gm, kind):
    return gm.world.events(0, kinds=[kind], limit=5000)


def night(gm, on=True):
    gm.schedule(1, "dusk" if on else "dawn", entity=gm.summary()["root"])
    gm.clock(step=2)


def trust(gm, who, n):
    gm.link(who, "Herders", "standing", {"value": n, "public": True})


def held(gm, who, kind):
    return sum(int(c["state"].get("count") or 1) for c in gm.world.children(gm._resolve(who))
               if c["state"].get("kind") == kind)


def test_a_promise_is_offered_gated_done_at_night_by_the_takers_hand_and_paid(camp):
    eng, gm, ada, cara, nico = camp
    assert "Jackal hunt" not in str(ada.act("jobs")["result"])  # carried, not offered: nobody sees it
    nico.act("offer_job", "Ada", params={"job": "Jackal hunt"})
    card = ada.act("jobs")["result"]["offered"]
    hunt = next(c for c in card if c["job"] == "Jackal hunt")
    assert hunt["giver"] == "Nico" and hunt["why_not"] == "Herders do not trust you enough for this yet"
    with pytest.raises(Rejected) as r:
        ada.act("take_job", params={"job": "Jackal hunt"})
    assert "trust" in r.value.reason
    trust(gm, "Ada", 1)
    ada.act("take_job", params={"job": "Jackal hunt"})
    assert gm.world.need(gm._resolve("Jackal hunt"))["state"]["holders"]
    ada.act("go", "Slope")
    ada.act("kill", "Jackal one")  # by day: it does not count
    assert not kinds(gm, "job_done")
    night(gm)
    ada.act("kill", "Jackal two")
    done = kinds(gm, "job_done")
    assert len(done) == 1 and done[0]["target_id"] == gm._resolve("Ada")
    paid = kinds(gm, "job_paid")[0]["payload"]
    assert paid["items"] == [{"kind": "flatbread", "count": 2}] and paid["standing"]["delta"] == 1
    assert held(gm, "Ada", "flatbread") == 2
    assert st(gm, "Herd")["safety"] == 1
    hunt = st(gm, "Jackal hunt")
    assert hunt["open"] is False and hunt["done_by"] == {gm._resolve("Ada"): 1} and "holders" not in hunt or not hunt["holders"]


def test_a_world_rule_opens_the_job_again(camp):
    eng, gm, ada, cara, nico = camp
    gm.patch("Jackal hunt", {"open": False})
    with pytest.raises(Rejected):
        nico.act("offer_job", "Cara", params={"job": "Jackal hunt"})
    gm.schedule(1, "job_reopen", entity="Jackal hunt", payload={"why": "a goat was taken"})
    gm.clock(step=2)
    assert st(gm, "Jackal hunt")["open"] is True and kinds(gm, "job_reopened")
    nico.act("offer_job", "Cara", params={"job": "Jackal hunt"})


def test_a_posting_is_anyones_here_within_its_slots_and_a_handing_over_is_the_work(camp):
    eng, gm, ada, cara, nico = camp
    posted = {c["job"] for c in ada.act("jobs")["result"]["offered"]}
    assert {"Water run", "Count the herd"} <= posted
    ada.act("take_job", params={"job": "Water run"})
    cara.act("take_job", params={"job": "Water run"})
    gm.spawn("person", gm._resolve("Fold"), "Dov", state={"water": 10})
    dov = eng.session("dov")
    dov.join("camp", "Dov")
    with pytest.raises(Rejected) as r:
        dov.act("take_job", params={"job": "Water run"})
    assert "others have taken it" in r.value.reason
    cara.act("give", "Nico", params={"item": "Water skin"})
    assert [e["target_id"] for e in kinds(gm, "job_done")] == [gm._resolve("Cara")]
    assert st(gm, "Water run")["open"] is True  # "always": the next one may take it
    dov.act("take_job", params={"job": "Water run"})


def test_a_job_fails_when_its_days_run_out_or_its_taker_drops_it(camp):
    eng, gm, ada, cara, nico = camp
    ada.act("take_job", params={"job": "Count the herd"})
    gm.clock(step=DAY + 5)
    failed = kinds(gm, "job_failed")
    assert failed and failed[0]["payload"]["why"] == "window"
    cara.act("take_job", params={"job": "Water run"})
    cara.act("drop_job", params={"job": "Water run"})
    assert kinds(gm, "job_failed")[-1]["payload"]["why"] == "dropped"
    assert not st(gm, "Water run").get("busy")
    with pytest.raises(Rejected):
        cara.act("drop_job", params={"job": "Water run"})


def test_driving_a_pack_off_counts_when_one_of_it_is_the_kind(camp):
    eng, gm, ada, cara, nico = camp
    ada.act("go", "Slope")
    ada.act("take_job", params={"job": "Drive the pack"})
    me, slope = gm._resolve("Ada"), gm._resolve("Slope")
    goat = gm.spawn("person", slope, "Stray goat", state={"species": "goat"})["id"]
    gm.schedule(1, "beast_driven_off", entity=slope, payload={"by": me, "hunters": [goat]})
    gm.clock(step=2)
    assert not kinds(gm, "job_done")
    gm.schedule(1, "beast_driven_off", entity=slope, payload={"by": me, "hunters": [goat, gm._resolve("Jackal one")]})
    gm.clock(step=2)
    assert [e["target_id"] for e in kinds(gm, "job_done")] == [me]
