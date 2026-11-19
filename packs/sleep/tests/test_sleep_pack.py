"""packs/sleep in a dice-free camp: a body lies down and is asleep, its own next deed wakes it, another wakes it with a
shake, and a seat going away can sleep. No d20 anywhere."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "camp", "name": "Camp", "seed": 3, "description": "A fire and two bedrolls.", "requires": ["village", "sleep"]}

def define(s):
    s.define_schema("person", extends="sleeper",
                    actions={"take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"}})

def populate(s):
    root = s.summary()["root"]
    camp = s.spawn("place", root, "Camp")["id"]
    s.spawn("person", camp, "Ada")
    s.spawn("person", camp, "Bel")
    s.spawn("thing", camp, "Stick", state={"portable": True})
    s.clock(run=False)
'''


@pytest.fixture
def camp(tmp_path):
    for p in ("village", "sleep"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "camp").mkdir(parents=True)
    (tmp_path / "worlds" / "camp" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "camp")
    ada, bel = eng.session("ada"), eng.session("bel")
    ada.join("camp", "Ada")
    bel.join("camp", "Bel")
    return eng, gm, ada, bel


def asleep(eng, name):
    w = eng.world("camp")
    return bool(w.find(name=name)[0]["state"].get("asleep"))


def kinds(eng, kind):
    w = eng.world("camp")
    return [e["payload"] for e in w.store.query("event", "world_id=? AND kind=?", (w.id, kind), order="seq")]


def test_sleep_lies_a_body_down_and_its_own_deed_wakes_it(camp):
    eng, gm, ada, bel = camp
    ada.act("sleep")
    assert asleep(eng, "Ada") and kinds(eng, "slept")
    with pytest.raises(Rejected):
        ada.act("sleep")  # asleep already
    ada.act("take", "Stick")
    assert not asleep(eng, "Ada") and kinds(eng, "woke")


def test_another_wakes_a_sleeper_with_a_shake(camp):
    eng, gm, ada, bel = camp
    ada.act("sleep")
    bel.act("wake", "Ada")
    assert not asleep(eng, "Ada") and kinds(eng, "woke")[-1]["why"] == "woken"
    with pytest.raises(Rejected) as r:
        bel.act("wake", "Ada")
    assert "awake" in r.value.reason


def test_a_seat_going_away_can_sleep(camp):
    eng, gm, ada, bel = camp
    assert ada.away(sleep=True)["asleep"] is True and asleep(eng, "Ada")
