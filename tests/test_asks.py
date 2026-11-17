"""ask: a guest asks the owner for something outside the fiction. Called bare it walks them through the kinds; a
missing field points forward with an example; the owner (and the readers the owner names, for shared asks) read and
answer; the asker reads the answer back in asks(), and perceive says it came; nothing in the world sees any of it."""

import pytest

from embody.ops import ASK_PER_HOUR, Rejected, call
from tests.test_flaws import player
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def test_called_bare_it_asks_nothing_and_walks_the_asker_through():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    out = sam.ask()
    assert out["ok"] is False and out["asked"] is None
    assert {"testing", "capability", "fix", "proposal", "seat", "quest", "help", "other"} <= set(out["kinds"])
    assert "credit" in out["fields"] and "CONTRIBUTING.md" in out["kinds"]["proposal"]["for"]
    assert out["kinds"]["testing"]["needs"] == ["what", "why"] and out["kinds"]["testing"]["example"]["kind"] == "testing"
    assert "report_flaw" in out["not_for"] and "share" in out["fields"]
    with pytest.raises(Rejected) as r:
        sam.ask("wishes", what="a dragon")
    assert "testing" in r.value.reason and "no arguments" in r.value.hint
    with pytest.raises(Rejected) as r:
        sam.ask("testing", what="a reviewer while I try to break trades")
    assert "needs why" in r.value.reason and "ask(kind='testing'" in r.value.hint
    with pytest.raises(Rejected) as r:
        sam.ask("quest", what="something to do", urgency="now")
    assert "low, normal, high" in r.value.reason
    with pytest.raises(Rejected) as r:
        sam.ask("quest", what="x" * 301)
    assert "one line" in r.value.hint
    with pytest.raises(Rejected) as r:
        sam.ask("quest", what="a lead", concerns=["Nobody at all"])
    assert "concerns names" in r.value.reason
    assert gm.asks()["asks"] == []


def test_an_ask_reaches_the_owner_and_the_answer_comes_back_through_the_world():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, inv = player(eng, gm)
    seq = w.store.next_seq(w.id)
    out = sam.ask("testing", what="a reviewer while I try to break the trade rules",
                  why="I want to see whether gifts farm standing; I stop when told", urgency="high")
    assert out["ok"] and out["status"] == "open" and out["id"].startswith("ask-")
    assert w.store.next_seq(w.id) == seq  # nothing in the world's log
    mine = sam.asks()
    assert mine["reader"] is False and len(mine["asks"]) == 1
    a = mine["asks"][0]
    assert a["kind"] == "testing" and a["urgency"] == "high" and a["share"] is True
    assert a["concerns"] == [{"id": i["Prisoner"], "name": "Prisoner"}] and "pid" not in a and "grant" not in a
    got = gm.asks()
    assert got["reader"] and got["asks"][0]["grant"] == inv["id"] and got["asks"][0]["role"] == "player"
    assert "answer_ask" in got["how"]
    with pytest.raises(Rejected) as r:
        gm.answer_ask(a["id"], "answered")
    assert "needs an answer" in r.value.reason
    with pytest.raises(Rejected) as r:
        sam.answer_ask(a["id"], "answered", "yes")
    assert "only the owner" in r.value.reason
    gm.answer_ask(a["id"], "answered", "Yes: Linnet watches the trades tonight; stop when she says.")
    assert "asks_notice" in sam.perceive()
    back = sam.asks()["asks"][0]
    assert back["status"] == "answered" and back["answer"].startswith("Yes: Linnet")
    assert back["history"][0]["status"] == "answered"
    assert "asks_notice" not in sam.perceive()  # reading the list marks it read
    assert sam.asks(status="open")["asks"] == [] and sam.asks(kind="testing")["asks"]


def test_readers_the_owner_names_see_only_shared_asks():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    gm.patch("Guard", {"playable": True})
    keep = gm.invite("narrator", label="Keeper")
    keeper = eng.session_for_token(keep["token"])
    keeper.use("two-rooms")
    shared = sam.ask("help", what="I cannot find the way out", why="the door is locked and I hold no key")["id"]
    private = sam.ask("other", what="may a friend join?", share=False)["id"]
    assert keeper.asks()["reader"] is False and keeper.asks()["asks"] == []
    with pytest.raises(Rejected):
        keeper.answer_ask(shared, "seen")
    with pytest.raises(Rejected) as r:
        gm.ask_readers(add=["no-such-grant"])
    assert "grants()" in r.value.hint
    assert gm.ask_readers(add=[keep["id"]])["readers"] == [keep["id"]]
    ids = [a["id"] for a in keeper.asks()["asks"]]
    assert ids == [shared]
    with pytest.raises(Rejected):
        keeper.answer_ask(private, "seen")
    keeper.answer_ask(shared, "escalated")
    assert {a["id"] for a in gm.asks()["asks"]} == {shared, private}
    assert sam.asks()["asks"][1]["status"] == "escalated"
    assert call(sam, "ask_readers", add=[keep["id"]])["ok"] is False
    gm.ask_readers(remove=[keep["id"]])
    assert keeper.asks()["reader"] is False


def test_a_proposal_carries_the_credit_its_asker_wants():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    with pytest.raises(Rejected) as r:
        sam.ask("proposal", what="name the nearest verb in a refusal")
    assert "needs why" in r.value.reason and "credit=" in r.value.hint
    with pytest.raises(Rejected):
        sam.ask("proposal", what="x", why="y", credit="z" * 81)
    sam.ask("proposal", what="name the nearest verb in a refusal", why="walk was refused; I lost two turns",
            credit="Sam of the cell")
    assert gm.asks(kind="proposal")["asks"][0]["credit"] == "Sam of the cell"
    assert sam.asks()["asks"][0]["credit"] == "Sam of the cell"


def test_a_hand_asks_a_few_an_hour():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    for n in range(ASK_PER_HOUR):
        sam.ask("quest", what=f"lead {n}")
    with pytest.raises(Rejected) as r:
        sam.ask("quest", what="one more")
    assert "this hour" in r.value.reason


def test_asks_are_kept_in_a_file_beside_the_database(tmp_path):
    from embody.asks import AskLog
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    eng.asks = AskLog(tmp_path / "asks.jsonl")
    aid = sam.ask("fix", what="the cups promise water", why="no verb fills them")["id"]
    gm.answer_ask(aid, "declined", "The cups are dry on purpose: try the well.")
    assert len((tmp_path / "asks.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    fresh = AskLog(tmp_path / "asks.jsonl")
    assert fresh.fold(w.id)[0]["status"] == "declined" and fresh.fold(w.id)[0]["news"] is True
