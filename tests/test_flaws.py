"""report_flaw: any hand tells the owner about a hole instead of using it; only the owner reads them (flaws), nothing
in the world sees them, and a hand reports at most a few an hour."""

import json

import pytest

from embody.asks import AskLog
from embody.ops import FLAW_PER_HOUR, Rejected, call
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def player(eng, gm):
    gm.patch("Prisoner", {"playable": True})
    inv = gm.invite("player", entity="Prisoner", label="Sam")
    s = eng.session_for_token(inv["token"])
    s.use("two-rooms")
    s.join("two-rooms", "Prisoner")
    return s, inv


def test_a_player_reports_a_hole_and_only_the_owner_reads_it():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, inv = player(eng, gm)
    seq = w.store.next_seq(w.id)
    out = sam.report_flaw("check can be rolled until it lands", how="1. check search\n2. again", severity="High")
    assert out["kept"] and "owner" in out["note"]
    assert w.store.next_seq(w.id) == seq  # nothing in the world's log
    got = gm.flaws()
    assert len(got) == 1 and got[0]["what"] == "check can be rolled until it lands" and got[0]["severity"] == "high"
    assert got[0]["how"].startswith("1. check") and got[0]["grant"] == inv["id"] and got[0]["role"] == "player"
    assert got[0]["body"] == w.find(name="Prisoner")[0]["id"]
    assert "not allowed" in call(sam, "flaws")["reason"] or call(sam, "flaws")["ok"] is False


def test_a_report_is_checked_and_a_hand_reports_a_few_an_hour():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    with pytest.raises(Rejected):
        sam.report_flaw("   ")
    with pytest.raises(Rejected) as why:
        sam.report_flaw("x", severity="urgent")
    assert "low, medium or high" in why.value.reason
    with pytest.raises(Rejected):
        sam.report_flaw("x" * 2001)
    for n in range(FLAW_PER_HOUR):
        sam.report_flaw(f"hole {n}")
    with pytest.raises(Rejected) as why:
        sam.report_flaw("one more")
    assert "this hour" in why.value.reason
    assert [r["what"] for r in gm.flaws(limit=2)] == [f"hole {FLAW_PER_HOUR - 1}", f"hole {FLAW_PER_HOUR - 2}"]


def test_reports_are_kept_in_the_asks_log_beside_the_database(tmp_path):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    eng.asks = AskLog(tmp_path / "asks.jsonl")
    out = sam.report_flaw("a hole")
    row = json.loads((tmp_path / "asks.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["what"] == "a hole" and row["world"] == "two-rooms" and row["kind"] == "flaw" and row["share"] is False
    assert row["id"] == out["id"] and gm.flaws()[0]["what"] == "a hole"


def test_the_owner_answers_a_flaw_and_its_reporter_hears_back():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    fid = sam.report_flaw("a verb writes hp", how="the steps", severity="high")["id"]
    got = gm.flaws()[0]
    assert got["id"] == fid and got["status"] == "open" and got["answer"] is None and "pid" not in got
    gm.answer_ask(fid, "answered", "closed in the next deploy, thank you")
    assert gm.flaws()[0]["status"] == "answered"
    assert "owner_answered" in sam.perceive()
    mine = sam.asks_to_owner()["asks"][0]
    assert mine["id"] == fid and mine["answer"] == "closed in the next deploy, thank you"
    assert "owner_answered" not in sam.perceive()  # read once listed
    # a reader the owner names never reads or answers a flaw: the owner's eyes only
    keep = gm.invite("narrator", label="Keeper")
    gm.ask_readers(add=[keep["id"]])
    k = eng.session_for_token(keep["token"])
    k.use("two-rooms")
    assert k.asks_to_owner()["asks"] == []
    with pytest.raises(Rejected):
        k.answer_ask(fid, "seen")


def test_flaws_do_not_use_up_the_asks_of_an_hour():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    for n in range(3):
        sam.report_flaw(f"hole {n}")
    assert sam.ask_owner("help", what="stuck in the cell", why="no way out")["ok"]


def test_reports_from_before_ids_come_in_once_and_can_be_answered(tmp_path):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, inv = player(eng, gm)
    eng.flaws_path = tmp_path / "flaw-reports.jsonl"
    old = {"at": "2026-11-16T11:34:06+00:00", "world": "two-rooms", "by": "Sam", "grant": inv["id"], "role": "player",
           "body": None, "severity": None, "what": "str.rstrip is not allowed", "how": ""}
    eng.flaws_path.write_text(json.dumps(old) + "\n", encoding="utf-8")
    got = gm.flaws()
    assert len(got) == 1 and got[0]["what"] == "str.rstrip is not allowed" and got[0]["id"].startswith("flaw-")
    assert len(gm.flaws()) == 1  # brought in once
    gm.answer_ask(got[0]["id"], "answered", "scripts may rstrip now")
    assert sam.asks_to_owner()["asks"][0]["answer"] == "scripts may rstrip now"
