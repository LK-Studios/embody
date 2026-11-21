"""The crew's lay hands, as a gift the world gives a body (state `lays_hands`), read by tend: a hurt body on its feet
gets 1d4 back, once in eight world hours, with no medicine and no water. Without the gift it is refused as before."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "flats", "name": "Flats", "seed": 5, "description": "Open sand and a well.", "requires": ["d20", "village"]}

from packs.d20.pack import install_rules

def define(s):
    s.define_schema("person", extends="combatant",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"}})

def populate(s):
    root = s.summary()["root"]
    install_rules(s, root)
    sand = s.spawn("place", root, "Sand", state={"open": True})["id"]
    s.spawn("person", sand, "Ada", state={"body": 3, "hp": 3})
    s.spawn("person", sand, "Bel", state={"body": 3, "hp": 2})
    s.spawn("person", sand, "Cass", state={"body": 3, "hp": 2})
    s.clock(run=False)
'''


@pytest.fixture
def flats(tmp_path):
    for p in ("village", "d20"):
        shutil.copytree(REPO / "packs" / p, tmp_path / "packs" / p, ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "packs" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "worlds" / "flats").mkdir(parents=True)
    (tmp_path / "worlds" / "flats" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "flats")
    return eng, gm


def test_a_gifted_body_lays_hands_on_someone_standing_once_per_rest(flats):
    eng, gm = flats
    gm.patch("Ada", {"lays_hands": True})
    p = eng.session("p")
    p.join("flats", "Ada")
    p.act("tend", "Bel")
    hp = int(gm.inspect("Bel")["state"]["hp"])
    assert 3 <= hp <= 6
    with pytest.raises(Rejected) as r:
        p.act("tend", "Cass")
    assert "spent" in r.value.reason


def test_an_ungifted_body_is_refused_as_before(flats):
    eng, gm = flats
    p = eng.session("p")
    p.join("flats", "Ada")
    with pytest.raises(Rejected) as r:
        p.act("tend", "Bel")
    assert "on their feet" in r.value.reason
