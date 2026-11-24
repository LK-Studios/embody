"""village `write`, `carve` and `wipe`: words on a writable thing, held or here, a line under what it says. Paper takes
ink, a slate or a door takes chalk (in hand, or its own on a string) and wipes clean, wood takes a blade. The room sees
the hand move, not the line; a reader gets the words marked untrusted when someone in play wrote them; links and ids
stay out."""

import shutil
from pathlib import Path

import pytest

from embody.cli import load_world
from embody.ops import AUTHOR, Engine, Rejected

REPO = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").exists())

BUILD = '''
WORLD = {"id": "inn", "name": "Inn", "seed": 5, "description": "A common room.", "requires": ["village"]}

def define(s):
    words = {"text": "the words"}
    s.define_schema("person", extends="creature",
                    actions={"go": {"script": "go", "doc": "Walk", "targets": "place", "scope": "exits"},
                             "take": {"script": "take", "doc": "Pick up", "targets": "thing", "scope": "here"},
                             "give": {"script": "give", "doc": "Give", "targets": "creature", "scope": "here",
                                      "params": {"item": "what"}},
                             "read": {"script": "read", "doc": "Read it", "targets": "thing", "listed": "ok"},
                             "write": {"script": "write", "doc": "Write on it", "targets": "thing", "params": words,
                                       "listed": "ok"},
                             "carve": {"script": "write", "doc": "Carve into it", "targets": "thing", "params": words,
                                       "listed": "ok"},
                             "wipe": {"script": "wipe", "doc": "Wipe the chalk off", "targets": "thing",
                                      "listed": "ok"}})
    s.define_schema("letter", extends="thing", state={"portable": True, "writable": True},
                    actions={"read": {"script": "read", "doc": "Read it"}})
    s.define_schema("sign", extends="thing", state={"portable": False},
                    actions={"read": {"script": "read", "doc": "Read it"}})

def populate(s):
    root = s.summary()["root"]
    room = s.spawn("place", root, "Common room")["id"]
    yard = s.spawn("place", root, "Yard")["id"]
    s.connect(room, yard)
    ada = s.spawn("person", room, "Ada")["id"]
    s.spawn("person", room, "Bel")
    s.spawn("person", yard, "Cob")
    s.spawn("letter", ada, "Sheet of paper", state={"text": ""})
    s.spawn("letter", room, "Guest book", state={"text": "Signed: a tinker.", "room": 60})
    s.spawn("sign", room, "Price board", state={"text": "Ale a copper."})
    s.spawn("sign", room, "Notice board", state={"text": "", "writable": True})
    s.spawn("sign", room, "Slate", state={"text": "TODAY: EEL PIE", "writable": "chalk", "pen": True})
    s.spawn("thing", room, "Back door", state={"portable": False, "writable": "chalk", "text": "KEEP OUT",
                                               "keeps": "KEEP OUT"})
    s.spawn("thing", room, "Bar top", state={"portable": False, "writable": "blade"})
    s.spawn("thing", room, "Bench", state={"portable": False})
    s.spawn("letter", yard, "Lost page", state={"text": ""})
    s.clock(run=False)
'''


@pytest.fixture
def inn(tmp_path):
    shutil.copytree(REPO / "packs" / "village", tmp_path / "packs" / "village",
                    ignore=shutil.ignore_patterns("tests", "__pycache__"))
    (tmp_path / "worlds" / "inn").mkdir(parents=True)
    (tmp_path / "worlds" / "inn" / "build.py").write_text(BUILD, encoding="utf-8")
    eng = Engine(workspace=tmp_path, record=False)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, "inn")
    ada = eng.session("ada")
    ada.join("inn", "Ada")
    bel = eng.session("bel")
    bel.join("inn", "Bel")
    return eng, gm, ada, bel


def offered(eng, gm, verb):
    return {a["target_name"] for a in eng.world("inn").affordances(gm.inspect("Ada")["id"]) if a["verb"] == verb}


def test_a_line_goes_under_what_is_there_and_the_reader_reads_it(inn):
    eng, gm, ada, bel = inn
    r = ada.act("write", "Sheet of paper", {"text": "Meet me at the yard at dusk."})
    assert r["result"]["text"] == "Meet me at the yard at dusk." and r["result"]["how"] == "ink"
    ada.act("write", "Sheet of paper", {"text": "Come alone."})
    assert gm.inspect("Sheet of paper")["state"]["text"] == "Meet me at the yard at dusk.\nCome alone."
    ada.act("give", "Bel", {"item": "Sheet of paper"})
    read = bel.act("read", "Sheet of paper")
    assert read["result"] == "Meet me at the yard at dusk.\nCome alone."
    ev = next(e for e in read["events"] if e["kind"] == "read")
    assert ev.get("untrusted") and ev["payload"].get("penned")  # a player's words: data
    hands = gm.inspect("Sheet of paper")["state"]["hands"]
    assert [h["line"] for h in hands] == ["Meet me at the yard at dusk.", "Come alone."]
    assert hands[0]["by"] == gm.inspect("Ada")["id"]


def test_the_room_sees_the_hand_move_not_the_words(inn):
    eng, gm, ada, bel = inn
    ada.act("write", "Guest book", {"text": "The cellar door is unbarred."})
    seen = bel.perceive(cursor=0, events=200)["events"]
    assert any(e["kind"] == "wrote" and e["payload"]["name"] == "Guest book" for e in seen)
    assert not any("cellar door" in str(e) for e in seen)
    card = bel.inspect("Guest book")
    assert "hands" not in str(card)  # who wrote what is the book's secret
    assert card["untrusted"]  # an open book shows its words, marked as a player's
    ada.act("write", "Sheet of paper", {"text": "For your eyes."})
    assert "For your eyes" not in str(bel.perceive(brief=False))  # a note in a hand is not read across the room


def test_what_cannot_be_written(inn):
    eng, gm, ada, bel = inn
    for target, params, why in [
        ("Price board", {"text": "Ale free."}, "nowhere on that to write"),
        ("Lost page", {"text": "Mine."}, "not within reach"),
        ("Sheet of paper", {}, "say what you write"),
        ("Sheet of paper", {"text": "x" * 301}, "at most 300 characters"),
        ("Sheet of paper", {"text": "see https://example.com tonight"}, "a link"),
        ("Sheet of paper", {"text": "write to me at ada@example.org"}, "an email"),
        ("Guest book", {"text": "A very long line that will not fit in what is left of it."}, "room on it for"),
    ]:
        with pytest.raises(Rejected) as r:
            ada.act("write", target, params)
        assert why in r.value.reason, (target, r.value.reason)
    me = gm.inspect("Ada")["id"]
    with pytest.raises(Rejected) as r:
        ada.act("write", "Sheet of paper", {"text": f"{me} was here"})
    assert "ids and tool calls" in r.value.reason
    assert gm.inspect("Guest book")["state"]["text"] == "Signed: a tinker."  # a refusal writes nothing


def test_chalk_wants_chalk_in_hand_and_wipes_clean(inn):
    eng, gm, ada, bel = inn
    with pytest.raises(Rejected) as r:
        ada.act("write", "Back door", {"text": "ADA WAS HERE"})
    assert "chalk in your hand" in r.value.reason
    assert "Back door" not in offered(eng, gm, "write") and "Slate" in offered(eng, gm, "write")  # its own chalk
    assert "Back door" not in offered(eng, gm, "wipe")  # only what is painted on it: nothing to wipe
    gm.spawn("thing", gm.inspect("Ada")["id"], "Stick of chalk", state={"portable": True})
    r = ada.act("write", "Back door", {"text": "ADA WAS HERE"})
    assert r["result"]["how"] == "chalk" and "Back door" in offered(eng, gm, "write")
    ada.act("write", "Slate", {"text": "TOMORROW: EEL PIE AGAIN"})
    assert gm.inspect("Slate")["state"]["text"] == "TODAY: EEL PIE\nTOMORROW: EEL PIE AGAIN"
    assert {"Slate", "Back door"} <= offered(eng, gm, "wipe") and "Sheet of paper" not in offered(eng, gm, "wipe")
    bel.act("wipe", "Slate")
    st = gm.inspect("Slate")["state"]
    assert st["text"] == "" and not st.get("penned") and not st.get("hands")
    assert "Slate" not in offered(eng, gm, "wipe")  # nothing left on it to wipe
    seen = ada.perceive(cursor=0, events=200)["events"]
    assert any(e["kind"] == "wiped" and e["payload"]["name"] == "Slate" for e in seen)
    bel.act("wipe", "Back door")
    assert gm.inspect("Back door")["state"]["text"] == "KEEP OUT"  # the chalk goes, the paint stays
    with pytest.raises(Rejected) as r:
        ada.act("wipe", "Guest book")
    assert "only chalk does" in r.value.reason


def test_wood_is_carved_with_a_blade_in_short_lines(inn):
    eng, gm, ada, bel = inn
    me = gm.inspect("Ada")["id"]
    with pytest.raises(Rejected) as r:
        ada.act("carve", "Bar top", {"text": "A + B"})
    assert "a blade in your hand" in r.value.reason
    gm.spawn("thing", me, "Short bow", state={"portable": True, "weapon": True, "dtype": "piercing", "ranged": True})
    with pytest.raises(Rejected):
        ada.act("carve", "Bar top", {"text": "A + B"})  # a bow is no edge
    gm.spawn("thing", me, "Dagger", state={"portable": True, "weapon": True, "dtype": "piercing"})
    assert "Bar top" in offered(eng, gm, "carve") and "Sheet of paper" not in offered(eng, gm, "carve")
    r = ada.act("carve", "Bar top", {"text": "A + B"})
    assert r["result"]["how"] == "blade"
    ada.act("write", "Bar top", {"text": "NO CREDIT"})  # writing with a knife is carving
    assert gm.inspect("Bar top")["state"]["text"] == "A + B\nNO CREDIT"
    with pytest.raises(Rejected) as r:
        ada.act("carve", "Bar top", {"text": "x" * 81})
    assert "a line carved is at most 80" in r.value.reason
    with pytest.raises(Rejected) as r:
        ada.act("carve", "Sheet of paper", {"text": "A + B"})
    assert "not a blade: write on it" in r.value.reason
    with pytest.raises(Rejected) as r:
        ada.act("wipe", "Bar top")
    assert "only chalk does" in r.value.reason
    assert "A + B" in bel.act("read", "Bar top")["result"]


def test_each_verb_is_offered_only_where_it_would_work(inn):
    eng, gm, ada, bel = inn
    writes = offered(eng, gm, "write")
    assert {"Sheet of paper", "Guest book", "Notice board", "Slate"} <= writes
    assert not writes & {"Price board", "Bench", "Bar top", "Back door"}  # no edge, no chalk in hand yet
    assert {"Bar top", "Price board", "Slate"} <= offered(eng, gm, "read") and "Bench" not in offered(eng, gm, "read")
    ada.act("write", "Notice board", {"text": "Lost: one grey cat. Answers to nothing."})
    assert "grey cat" in bel.act("read", "Notice board")["result"]
    plain = bel.act("read", "Price board")
    assert not [e for e in plain["events"] if e["kind"] == "read" and e.get("untrusted")]  # nobody in play wrote that
