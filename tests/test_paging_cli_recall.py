"""The CLI reaches the paged ops with their window flags, and recall pages its about-view back from a cursor."""

import json

from pathlib import Path

from embody.cli import load_world, main as cli_main
from embody.ops import AUTHOR, Engine
from tests.test_round4 import ferry  # noqa: F401  (the sample village, saved into a database)


def _load(db):
    ferry(str(db))  # the sample village, saved into a fresh database


def test_cli_paged_lists_take_their_window_flags(tmp_path, capsys):
    db = tmp_path / "w.db"
    _load(db)
    capsys.readouterr()
    assert cli_main(["--db", str(db), "--author", "--as", "gm", "--world", "ferry-at-dusk", "schemas", "--limit", "1"]) == 0
    one = json.loads(capsys.readouterr().out)
    assert len(one) == 1
    assert cli_main(["--db", str(db), "--author", "--as", "gm", "--world", "ferry-at-dusk", "schemas", "--limit", "1", "--offset", "1000"]) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert cli_main(["--db", str(db), "--author", "--as", "gm", "--world", "ferry-at-dusk", "schemas", "--sort=-id"]) == 0
    ids = [s["id"] for s in json.loads(capsys.readouterr().out)]
    assert ids == sorted(ids, reverse=True)


def test_cli_owner_lists_take_flags_and_refuse_a_bad_window(tmp_path, capsys):
    db = tmp_path / "w.db"
    _load(db)
    capsys.readouterr()
    assert cli_main(["--db", str(db), "--author", "--as", "gm", "--world", "ferry-at-dusk", "requests", "--limit", "5"]) == 0
    assert json.loads(capsys.readouterr().out) == []  # no seat requests in a fresh database
    rc = cli_main(["--db", str(db), "--author", "--as", "gm", "--world", "ferry-at-dusk", "flaws", "--limit", "0"])
    assert rc != 0  # the range is refused, the same way the door refuses it
    capsys.readouterr()


def test_recall_about_pages_back_from_a_before_cursor(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    eng = Engine(workspace=repo)
    gm = eng.session("gm", capabilities=[AUTHOR])
    load_world(gm, repo / "examples" / "ferry-at-dusk")
    you = eng.session("you")
    you.join("ferry-at-dusk", "Traveler")
    for k in range(4):
        you.say(f"line {k}", to="Mara")
    w = eng.world("ferry-at-dusk")
    says = w.store.query("event", "world_id=? AND kind='say'", (w.id,), order="seq")
    cut = max(r["seq"] for r in says)  # the newest line: a page before it leaves it out
    full = you.recall(about="Mara")["between"]
    before = you.recall(about="Mara", before=cut)["between"]
    assert len(before) < len(full)
    assert len(you.recall(about="Mara", before=10**9)["between"]) == len(full)  # past the newest: the same page
