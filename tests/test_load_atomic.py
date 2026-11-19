"""A world load is one transaction: a rejection anywhere in an upgrade (or a fresh build) undoes everything the load
wrote, and says so, so a world is never left half upgraded. Inside it, an op that rolls back undoes only its own part.
A placement at a landmark that is not there names the thing being placed and the place it looked in."""

import pytest

from embody.ops import AUTHOR, Engine
from embody.workspace import load_world
from embody.world import Rejected

BUILD = '''
from pathlib import Path
WORLD = {"id": "tiny", "name": "Tiny", "seed": 1, "requires": []}

def define(s):
    s.define_schema("well", extends="thing", doc="a well")

def populate(s):
    s.spawn("place", s.world.root_id, "Square")

def upgrade(s):
    s.define_schema("bucket", extends="thing", doc="a bucket")
    s.spawn("place", s.world.root_id, "Mill")
    if (Path(__file__).parent / "BREAK").exists():
        b = s.spawn("bucket", "Square", "Bucket")
        s.layout(placements=[{"entity": b["id"], "at": "the old well"}])
'''


def tiny(tmp_path):
    ws = tmp_path / "ws"
    (ws / "worlds" / "tiny" / "scripts").mkdir(parents=True)
    (ws / "packs").mkdir()
    (ws / "worlds" / "tiny" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(tmp_path / "w.db", workspace=ws, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "tiny")
    return eng, gm, ws / "worlds" / "tiny"


def counts(eng, wid="tiny"):
    st = eng.store
    return {t: st.count(t, "world_id=?", (wid,)) for t in ("schema", "entity", "event")}


def test_a_rejected_upgrade_keeps_nothing(tmp_path):
    eng, gm, folder = tiny(tmp_path)
    before = counts(eng)
    (folder / "BREAK").write_text("", encoding="utf-8")
    with pytest.raises(Rejected) as r:
        load_world(gm, "tiny", upgrade=True)
    assert "Nothing of this load was kept" in r.value.reason
    assert counts(eng) == before
    assert not gm.world.find(name="Mill") and eng.store.get("schema", "tiny", "bucket") is None
    (folder / "BREAK").unlink()
    load_world(gm, "tiny", upgrade=True)  # the same world upgrades cleanly afterwards
    assert gm.world.find(name="Mill")


def test_the_landmark_refusal_names_what_was_placed_and_where_it_looked(tmp_path):
    eng, gm, folder = tiny(tmp_path)
    (folder / "BREAK").write_text("", encoding="utf-8")
    with pytest.raises(Rejected) as r:
        load_world(gm, "tiny", upgrade=True)
    square = gm.world.find(name="Square")[0]["id"]
    assert r.value.reason.startswith("placing Bucket (") and f"in Square ({square}), where Bucket is" in r.value.reason


def test_an_inner_rollback_undoes_only_its_own_part(tmp_path):
    eng = Engine(tmp_path / "w.db", record=False)
    st = eng.store
    gm = eng.session("gm", capabilities=[AUTHOR])
    gm.create_world("Nest", id="nest")
    n = st.count("entity", "world_id=?", ("nest",))
    st.begin()
    gm.spawn("place", gm.world.root_id, "Kept")
    st.begin()
    gm.spawn("place", gm.world.root_id, "Dropped")
    st.rollback()
    st.commit()
    eng._worlds.clear()
    assert st.count("entity", "world_id=?", ("nest",)) == n + 1
    assert gm.world.find(name="Kept") and not gm.world.find(name="Dropped")
