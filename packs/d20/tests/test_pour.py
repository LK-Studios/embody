"""d20 pour: a skin's water goes into a store beside you (a cask, a jar, a cistern), another skin, or someone's skin,
all of it or `amount` draws, never past the store's capacity; the rest stays in the skin."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "hold", "name": "Hold", "seed": 5, "description": "A hold with jars, a cask and a well outside.",
         "requires": ["d20", "village"]}

from packs.d20.pack import install_rules

def define(s):
    s.define_schema("person", extends="combatant",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"}})

def populate(s):
    root = s.summary()["root"]
    install_rules(s, root)
    hold = s.spawn("place", root, "Hold")["id"]
    yard = s.spawn("place", root, "Yard", state={"water_source": True})["id"]
    s.connect(hold, yard)
    s.spawn("thing", hold, "Jars", state={"portable": False, "water_source": True, "left": 10, "capacity": 12})
    s.spawn("thing", hold, "Cask", state={"portable": False, "water_source": True, "left": 0})
    s.spawn("thing", hold, "Spring", state={"portable": False, "water_source": True})
    s.spawn("thing", hold, "Stool", state={"portable": False})
    ada = s.spawn("person", hold, "Ada")["id"]
    s.spawn("waterskin", ada, "Ada's skin", state={"left": 3})
    s.spawn("waterskin", ada, "Spare skin", state={"left": 0})
    bel = s.spawn("person", hold, "Bel")["id"]
    s.spawn("waterskin", bel, "Bel's skin", state={"left": 1})
    s.spawn("thing", yard, "Trough", state={"portable": False, "water_source": True, "left": 0})
    s.clock(run=False)
'''


@pytest.fixture
def hold(tmp_path):
    for p in ("village", "d20"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "packs" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "worlds" / "hold").mkdir(parents=True)
    (tmp_path / "worlds" / "hold" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "hold")
    ada = eng.session("ada")
    ada.join("hold", "Ada")
    return eng, gm, ada


def left(gm, name):
    return gm.inspect(name)["state"]["left"]


def poured(r):
    return [e["payload"] for e in r["events"] if e["kind"] == "poured"]


def test_pour_fills_a_store_up_to_its_capacity_and_keeps_the_rest(hold):
    eng, gm, ada = hold
    # listed only where it would work: the stores with room and Bel's skin, not the spring, the stool or a full store
    assert sorted(a["target_name"] for a in ada.perceive()["affordances"] if a["verb"] == "pour") == ["Bel", "Cask", "Jars"]
    r = ada.act("pour", "Jars")
    assert left(gm, "Jars") == 12 and left(gm, "Ada's skin") == 1  # two fit, one stays in the skin
    p = poured(r)[0]
    assert p["amount"] == 2 and p["left"] == 12 and p["kept"] == 1
    assert p["by"] == gm.inspect("Ada")["id"] and p["store"] == gm.inspect("Jars")["id"]
    assert p["item"] == gm.inspect("Ada's skin")["id"]
    with pytest.raises(Rejected) as ex:
        ada.act("pour", "Jars")
    assert "full (12 of 12)" in str(ex.value) and left(gm, "Ada's skin") == 1
    # a store with no capacity takes all of it
    ada.act("pour", "Cask")
    assert left(gm, "Cask") == 1 and left(gm, "Ada's skin") == 0
    assert gm.inspect("Ada's skin")["state"]["description"] == "A goatskin, slack and dry."


def test_pour_an_amount_from_a_named_skin_and_into_another_body(hold):
    eng, gm, ada = hold
    gm.patch("Spare skin", {"left": 2})
    ada.act("pour", "Cask", params={"item": "Spare skin", "amount": 1})
    assert left(gm, "Cask") == 1 and left(gm, "Spare skin") == 1 and left(gm, "Ada's skin") == 3
    r = ada.act("pour", "Bel", params={"amount": 1})  # into Bel's skin; the first skin Ada holds with water in it
    assert left(gm, "Bel's skin") == 2 and left(gm, "Ada's skin") == 2
    assert poured(r)[0]["store"] == gm.inspect("Bel's skin")["id"]


def test_pour_refuses_in_place_and_says_what_would_work(hold):
    eng, gm, ada = hold

    def refused(target, **params):
        with pytest.raises(Rejected) as ex:
            ada.act("pour", target, params=params or None)
        return str(ex.value)

    assert "never runs dry" in refused("Spring")
    assert "holds no water" in refused("Stool")
    with pytest.raises(Rejected) as ex:  # the engine's reach says where to go
        ada.act("pour", "Trough")
    assert "not within reach" in str(ex.value) and "Yard" in (ex.value.hint or "")
    assert "nothing called Rope" in refused("Cask", item="Rope")
    assert "is empty" in refused("Cask", item="Spare skin")
    assert "1 or more" in refused("Cask", amount=0)
    gm.patch("Bel's skin", {"left": 3})
    assert "no skin with room" in refused("Bel")
    gm.patch("Ada's skin", {"left": 0})
    assert "fill a skin at a source first" in refused("Cask")
    assert left(gm, "Cask") == 0 and left(gm, "Jars") == 10
