"""report_flaw: any hand tells the owner about a hole instead of using it; only the owner reads them (flaws), nothing
in the world sees them, and a hand reports at most a few an hour."""

import json

import pytest

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


def test_reports_are_kept_in_a_file_beside_the_database(tmp_path):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    eng.flaws_path = tmp_path / "flaw-reports.jsonl"
    sam.report_flaw("a hole")
    row = json.loads(eng.flaws_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["what"] == "a hole" and row["world"] == "two-rooms"
    assert gm.flaws()[0]["what"] == "a hole"
