"""perceive, short enough to say aloud (Klhyts Refuge, 2026-11-23: a player's agent on a voice client could not read the
scene, 68,000 characters at the docks; the owner: "it needs to be enough that could be spoken to and listened to").
brief=true gives the place and each person in a glance, things, exits and what you hold by name, and the verbs you
could use now with whom; a world's root `perceive_brief` makes it the default, and brief=false gives everything."""

import json
import shutil
from pathlib import Path

from embody.cli import load_world
from embody.ops import AUTHOR, Engine

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

LONG = ("A slab of a man on a bollard by the warehouse door, cudgel across his knees. He has not moved in an hour and "
        "does not mean to, and the planks around him are dark with spat tobacco. ") * 3

BUILD = '''
WORLD = {"id": "pier", "name": "The pier", "seed": 7, "description": "A pier at night.", "requires": ["village"]}

def define(s):
    s.define_schema("person", extends="creature",
                    actions={"talk": {"script": "talk", "doc": "Talk to someone", "targets": "creature", "scope": "here",
                                      "params": {"about": "the topic"}}},
                    listeners=[{"script": "person_on", "kinds": ["talked"], "unless_embodied": True}])

def populate(s):
    root = s.summary()["root"]
    pier = s.spawn("place", root, "Pier", state={"description": "Tarred planks on fat pilings. " + "Lamps. " * 80,
                                                  "short": "Tarred planks and lamplight."})["id"]
    s.spawn("place", root, "Street", state={"description": "A street."})
    s.connect(pier, s.find(name="Street")[0]["id"])
    s.spawn("person", pier, "Kalypso", state={"playable": True})
    s.spawn("person", pier, "Brask", state={"description": %r, "seen_as": "the slab of a man with the cudgel"})
    s.spawn("person", pier, "Varn", state={"description": %r})
    s.spawn("thing", pier, "Rope", state={"portable": True, "description": "A coil of rope."})
    s.clock(run=False)
''' % (LONG, "A thin fisherman mending a net with his teeth. " + LONG)


def pier(tmp_path, brief_default=False):
    ws = tmp_path / "ws"
    shutil.copytree(REPO / "packs" / "village", ws / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (ws / "worlds" / "pier").mkdir(parents=True)
    (ws / "worlds" / "pier" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(None, workspace=ws, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "pier")
    if brief_default:
        gm.patch(gm.summary()["root"], {"perceive_brief": True})
    kal = eng.session("kal")
    kal.join("pier", "Kalypso")
    return eng, gm, kal


def test_brief_says_each_in_a_glance(tmp_path):
    eng, gm, kal = pier(tmp_path)
    full = kal.perceive()
    b = kal.perceive(brief=True)
    assert len(json.dumps(b)) < len(json.dumps(full)) / 3
    assert b["here"]["looks"] == "Tarred planks and lamplight."  # the place's own short line
    looks = {p["name"]: p["looks"] for p in b["people"]}
    assert looks["Brask"] == "the slab of a man with the cudgel"  # seen_as
    assert looks["Varn"] == "A thin fisherman mending a net with his teeth."  # no line: the first sentence
    assert [t["name"] for t in b["things"]] == ["Rope"] and b["exits"] == ["Street"]
    assert "talk: anyone here" in b["verbs"]
    assert "more" in b and "present" not in b and "affordances" not in b


def test_a_world_makes_it_the_default(tmp_path):
    eng, gm, kal = pier(tmp_path, brief_default=True)
    assert "people" in kal.perceive() and "people" in kal.join("pier", "Kalypso")
    assert "present" in kal.perceive(brief=False)
    assert "present" in gm.perceive(from_entity="Brask")  # perceiving from another body is the author's full view


def test_a_mind_keeps_its_brief_and_notes_in_the_short_view(tmp_path):
    # Klhyts Refuge, 2026-11-24: an NPC's whole card ran to 80,000 characters and minds played without their brief
    from embody.grants import MIND
    eng, gm, kal = pier(tmp_path, brief_default=True)
    for name in ("Brask", "Kalypso"):
        gm.patch(gm.find(name=name)[0]["id"], {"brief": f"You are {name}."})
    gm.remember("Nobody passes the door.", entity="Brask")
    b = eng.session("brask", role=MIND).join("pier", "Brask")
    assert b["you"]["brief"] == "You are Brask." and b["you"]["memory"][0]["text"] == "Nobody passes the door."
    assert "people" in b  # still the short view
    assert "brief" not in kal.perceive()["you"]  # a player's short card stays short


def test_a_long_description_is_cut_at_a_word(tmp_path):
    from embody.ops import _glance
    line = _glance({"state": {"description": "word " * 100}})
    assert len(line) <= 163 and line.endswith("...") and not line.endswith(" ...")
