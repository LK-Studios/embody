"""Whose move it is (a player's agent in Klhyts Refuge, 2026-11-23: "Keep a list of who owes whom an answer ... Then any
agent can just ask 'who's waiting on me?' and 'who am I waiting on?'"; "Let a watch fire when a friend sits down"; the
waiting habit in the join reply). A line to a character someone plays, or a talk to one, owes an answer; a line they
hear from the one who owes it pays it; people nobody plays owe nothing; held(name) wakes a watch when a friend's
character is picked up again."""

import shutil
from pathlib import Path

from embody.cli import load_world
from embody.ops import AUTHOR, Engine

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "pier", "name": "The pier", "seed": 7, "description": "A pier at night.", "requires": ["village"]}

def define(s):
    s.define_schema("person", extends="creature",
                    actions={"talk": {"script": "talk", "doc": "Talk to someone", "targets": "creature", "scope": "here",
                                      "params": {"about": "the topic"}}},
                    listeners=[{"script": "person_on", "kinds": ["talked"], "unless_embodied": True}])

def populate(s):
    root = s.summary()["root"]
    pier = s.spawn("place", root, "Pier")["id"]
    s.spawn("person", pier, "Kalypso", state={"playable": True})
    s.spawn("person", pier, "Joe", state={"playable": True})
    s.spawn("person", pier, "Varn", state={"default_line": "Varn spits in the water."})
    s.clock(run=False)
'''


def pier(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(REPO / "packs" / "village", ws / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (ws / "worlds" / "pier").mkdir(parents=True)
    (ws / "worlds" / "pier" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(None, workspace=ws, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "pier")
    kal = eng.session("kal")
    kal.join("pier", "Kalypso")
    joe = eng.session("joe")
    joe.join("pier", "Joe")
    return eng, gm, kal, joe


def names(rows):
    return [r["name"] for r in rows]


def test_a_line_to_a_friend_owes_an_answer_and_their_answer_pays_it(tmp_path):
    eng, gm, kal, joe = pier(tmp_path)
    joe.say("Ahoy, what brings a sailor to the pier?", to="Kalypso")
    o = kal.owed()
    assert names(o["you_owe"]) == ["Joe"] and o["you_owe"][0]["said"].startswith("Ahoy") and o["you_owe"][0]["held"]
    assert names(joe.owed()["owed_you"]) == ["Kalypso"]
    assert kal.perceive()["owed"] == {"you_owe": ["Joe"], "owed_you": []}
    assert not [r for r in kal.perceive()["relations"] if r["relation"] == "owes_answer"]
    kal.say("The sea, and a beard I have not earned.")  # to the room, in Joe's hearing: paid
    assert kal.owed() == {"you_owe": [], "owed_you": []} and joe.owed() == {"you_owe": [], "owed_you": []}
    assert "owed" not in kal.perceive()


def test_a_name_at_the_start_owes_one_and_a_talk_does_too(tmp_path):
    eng, gm, kal, joe = pier(tmp_path)
    kal.say("Joe, is the rum any good here?")
    assert names(joe.owed()["you_owe"]) == ["Kalypso"]
    joe.act("talk", "Kalypso", {"about": "the rum, which is terrible"})  # a deed done to her pays it, and owes one back
    assert joe.owed()["you_owe"] == [] and names(kal.owed()["you_owe"]) == ["Joe"]


def test_people_nobody_plays_owe_nothing(tmp_path):
    eng, gm, kal, joe = pier(tmp_path)
    joe.say("Evening.", to="Varn")
    joe.act("talk", "Varn", {"about": "the fish"})
    assert joe.owed() == {"you_owe": [], "owed_you": []}
    kal.leave()  # nobody plays Kalypso now, and no grant keeps her: a line to her owes nothing
    joe.say("Kalypso, you there?")
    assert joe.owed()["owed_you"] == []


def test_a_watch_wakes_when_a_friend_sits_down(tmp_path):
    eng, gm, kal, joe = pier(tmp_path)
    kal.leave()
    r = joe.wait(until="held('Kalypso')", timeout=0.2)
    assert not r.get("fired")
    kal2 = eng.session("kal")
    kal2.join("pier", "Kalypso")
    assert joe.wait(until="held('Kalypso')", timeout=0.2).get("fired")


def test_join_tells_a_player_how_to_wait(tmp_path):
    eng, gm, kal, joe = pier(tmp_path)
    me = eng.session("ned")
    gm.spawn("person", gm.inspect("Pier")["id"], "Ned", state={"playable": True})
    b = me.join("pier", "Ned")["briefing"]
    text = " ".join(b["waiting"])
    assert "owed()" in text and "held('<name>')" in text and "away(answer=" in text and "heard(''" in text
