"""Positions: one rule for where everything is (own, a grid cell, or what carries it), landmarks to place by name,
verify() to audit a subtree with a fix for each problem, and true spots for what is put down or walks in."""

from pathlib import Path

import pytest

from embody.cli import load_world
from embody.layout import ground
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())


def _laid(tmp_path):
    eng = Engine(tmp_path / "w.db", workspace=REPO, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, REPO / "examples" / "ferry-at-dusk")
    gm.layout(frame={"units": "m"}, placements=[
        {"entity": "Ashford Square", "at": [0, 0, 0], "radius": 30,
         "landmarks": {"the well": {"at": [5, 5, 0], "radius": 3}, "the notice board": {"at": [-10, 0, 0], "radius": 2}}},
        {"entity": "Pell's Mill", "at": [100, 0, 0], "radius": 20}],
        paths=[{"a": "Ashford Square", "b": "Pell's Mill", "route": [[25, 0, 0], [85, 0, 0]]}])
    gm.layout(placements=[{"entity": "Well", "at": [5, 5, 0], "radius": 1}])
    return eng, gm


def test_every_entity_resolves_own_or_inherited_and_map_says_which(tmp_path):
    eng, gm = _laid(tmp_path)
    m = gm.map(under="Ashford Square", depth=2)
    rows = {r["name"]: r for r in m["entities"]}
    assert rows["Well"]["how"] == "own" and rows["Well"]["spot"] == "at the well"
    assert rows["Tinderbox"]["how"] == "inherited" and rows["Tinderbox"]["from"] == "Mara"
    assert "Mara" in m["no_spot"]["names"]  # directly in a place, only the square's centre
    assert gm.measure("Tinderbox")["a"]["from"] == "Mara"


def test_verify_lists_each_problem_with_a_fix_and_can_apply_it(tmp_path):
    eng, gm = _laid(tmp_path)
    gm.layout(placements=[{"entity": "Bone", "at": [5, 5, 0]}, {"entity": "Bench", "at": [200, 0, 0]}])
    v = gm.verify(under="Ashford Square", limit=200)
    by = {r["name"]: r for r in v["page"]}
    assert by["Mara"]["problem"] == "no position" and "the well" in by["Mara"]["fix"]["or"]
    assert by["Bone"]["problem"] == "inside something solid" and by["Bone"]["fix"]["or_move_into"] == "Well"
    assert by["Bench"]["problem"] == "outside its container"
    assert "Tinderbox" not in by  # it rides on Mara
    assert v["next"] is None and v["by_problem"]["no position"] >= 1

    assert "Ashford Square" not in v.get("no_landmarks", {}).get("places", [])
    assert "Pell's Mill" in gm.verify()["no_landmarks"]["places"]  # Hob stands there and the mill names no spots
    assert len({tuple(r["fix"]["at"]) for r in v["page"] if isinstance(r.get("fix"), dict)}) == len(
        [r for r in v["page"] if isinstance(r.get("fix"), dict)])  # no two suggestions share a spot

    one = gm.verify(under="Ashford Square", limit=1)
    assert len(one["page"]) == 1 and one["next"] == 1

    fixed = gm.verify(under="Ashford Square", limit=200, apply=True)
    assert fixed["applied"] == v["problems"]
    assert gm.verify(under="Ashford Square")["problems"] == 0


def test_place_by_landmark_and_perceive_names_the_spot(tmp_path):
    eng, gm = _laid(tmp_path)
    lantern = gm.spawn("thing", "Ashford Square", "Lantern", at="the well")
    at = lantern["state"]["layout"]["at"]
    assert ground(at, [5, 5, 0]) <= 3 and ground(at, [5, 5, 0]) > 1  # by the well, not in it
    assert "position_notice" not in lantern
    with pytest.raises(Rejected) as r:
        gm.spawn("thing", "Ashford Square", "Pail", at="the gallows")
    assert "the well" in r.value.hint
    bare = gm.spawn("thing", "Ashford Square", "Pail")
    assert "no spot of its own" in bare["position_notice"] and "the well" in bare["position_notice"]

    gm.move("Traveler", "Ashford Square", at="the notice board")
    p = eng.session("pc")
    p.join("ferry-at-dusk", "Traveler")
    b = p.perceive()
    assert b["you"]["spot"] in ("at the notice board", "by the notice board")
    gm.layout(placements=[{"entity": "Traveler", "at": "Lantern"}])  # beside a thing, by its name
    assert ground(gm.measure("Traveler")["a"]["at"], at) <= 4


def test_what_is_put_down_or_walks_in_keeps_a_true_spot(tmp_path):
    eng, gm = _laid(tmp_path)
    gm.move("Traveler", "Ashford Square", at=[10, -10, 0])
    lantern = gm.spawn("thing", "Traveler", "Lantern")["id"]
    gm.move(lantern, "Ashford Square")  # put down: where the holder stands
    assert ground(gm.measure(lantern)["a"]["at"], [10, -10, 0]) <= 2
    gm.move("Traveler", "Pell's Mill")  # walked in: where the way comes in
    a = gm.measure("Traveler")["a"]
    assert a["how"] == "own" and ground(a["at"], [85, 0, 0]) <= 4
    gm.move("Traveler", "The Reeds")  # no drawn way: no spot, as before
    w = eng.world("ferry-at-dusk")
    assert "at" not in (w.get(gm.inspect("Traveler")["id"])["state"].get("layout") or {})


def test_perceive_says_how_far_across_the_place_each_thing_is(tmp_path):
    # 2026-11-21, a world builder: agents bunched at the door because every present thing read as equally near
    eng, gm = _laid(tmp_path)
    gm.layout(placements=[{"entity": "Mara", "at": [5, 4, 0]}, {"entity": "Bench", "at": [8, 5, 0]},
                          {"entity": "Bone", "at": [-10, 0, 0]}])
    seen = {c["name"]: c for c in gm.perceive(from_entity="Mara")["present"]}
    assert seen["Well"]["from_you"] == "beside" and seen["Bench"]["from_you"] == "here"
    assert seen["Bone"]["from_you"] == "across"
    assert all("from_you" not in c for n, c in seen.items() if n not in ("Well", "Bench", "Bone"))  # no spot, no band


def test_a_low_line_is_heard_in_full_only_near_the_speaker(tmp_path):
    # 2026-11-21, a world builder: a line said anywhere in a place reached everyone in it, so nobody stepped closer
    eng, gm = _laid(tmp_path)
    sq = gm.inspect("Ashford Square")["id"]
    for name, at in [("Ana", [0, 0, 0]), ("Ben", [2, 0, 0]), ("Cal", [12, 0, 0])]:
        gm.spawn("person", sq, name)
        gm.layout(placements=[{"entity": name, "at": at}])
    seats = {}
    for name in ["Ana", "Ben", "Cal"]:
        seats[name] = eng.session(name.lower())
        seats[name].join(gm.world.id, name)
        seats[name].perceive()
    r = seats["Ana"].say("Meet me at the mill after dark.", low=True)
    assert r["heard_by"] == ["Ben"]

    def line(name):
        return [e["payload"] for e in seats[name].perceive()["events"] if e["kind"] == "say"][-1]
    near = line("Ben")
    assert near["text"] == "Meet me at the mill after dark." and "near" not in near
    far = line("Cal")
    assert far["low"] and far["heard"] is False and "text" not in far and "near" not in far
    seats["Ana"].say("And you, Cal.", to="Cal", low=True)
    assert line("Cal")["text"] == "And you, Cal."  # the one it is said to hears it, however far
    alone = seats["Cal"].say("Nobody hears this.", low=True)
    assert alone["heard_by"] == [] and "step closer" in alone["note"]
    assert line("Ana")["heard"] is False


def test_a_line_that_ends_its_speaker_still_returns():
    # 2026-11-22, a world build: a safe word that closed a dream destroyed the sim body inside its own say
    from tests.test_ops import engine_with_two_rooms
    eng, w, i = engine_with_two_rooms()
    w.define_script("safe_word", "def on(ctx, ev):\n    if 'red' in str(ev.payload.get('text')):\n"
                                 "        ctx.destroy(ev.actor)\n")
    w.define_schema("token", extends="thing", state={"portable": True},
                    listeners=[{"script": "safe_word", "holder": True, "kinds": ["say"]}])
    w.set_meta({"voice_radius": 20})
    for low in (False, True):
        sim = w.spawn("person", i["Cell"], "Sim")
        w.spawn("token", sim, "Token")
        s = eng.session(f"sim{low}")
        s.join("two-rooms", "Sim")
        out = s.say("red", low=low)
        assert out["ok"] and "heard_by" not in out and w.get(sim) is None


def test_a_voice_carries_only_so_far_across_a_wide_place_and_a_shout_further(tmp_path):
    # 2026-11-21, a world builder: on a fork a player 600 m across one open place was heard in full
    eng, gm = _laid(tmp_path)
    sq = gm.inspect("Ashford Square")["id"]
    for name, at in [("Ana", [0, 0, 0]), ("Ben", [15, 0, 0]), ("Cal", [60, 0, 0])]:
        gm.spawn("person", sq, name)
        gm.layout(placements=[{"entity": name, "at": at}])
    gm.layout(placements=[{"entity": "Mara", "at": [100, 0, 0]}, {"entity": "Traveler", "at": [100, 5, 0]}])
    seats = {}
    for name in ["Ana", "Ben", "Cal"]:
        seats[name] = eng.session(name.lower())
        seats[name].join(gm.world.id, name)
        seats[name].perceive()

    def line(name):
        return [e["payload"] for e in seats[name].perceive()["events"] if e["kind"] == "say"][-1]
    r = seats["Ana"].say("Anyone there?")
    assert "heard_by" not in r and line("Cal")["text"] == "Anyone there?"  # a world with no voice range hears as before
    gm.world.set_meta({"voice_radius": 20})
    assert seats["Ana"].say("Over here.")["heard_by"] == ["Ben"]
    near = line("Ben")
    assert near["text"] == "Over here." and "far" not in near
    far = line("Cal")
    assert far["too_far"] and far["heard"] is False and "text" not in far and "far" not in far
    r = seats["Ana"].say("OVER HERE.", loud=True)  # a shout carries four times the voice
    shout = line("Cal")
    assert r["heard_by"] == ["Ben", "Cal"] and shout["text"] == "OVER HERE." and shout["tone"] == "shout"
    seats["Ana"].say("Just you, Cal.", to="Cal")
    assert line("Cal")["text"] == "Just you, Cal."  # the one it is said to hears it, however far
    gm.patch(sq, {"voice_radius": 10})  # a place may carry a voice less far than the world
    alone = seats["Ana"].say("Ben?")
    assert alone["heard_by"] == [] and "loud=true" in alone["note"] and line("Ben")["too_far"]
    with pytest.raises(Rejected, match="low or loud"):
        seats["Ana"].say("Both.", low=True, loud=True)
