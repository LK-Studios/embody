"""Paged logs: requests takes offset and a side filter; the rows come newest first and a bad page is refused."""

import json

import pytest

from embody.ops import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def _write_requests(path, world, sides):
    rows = [{"at": f"2026-11-{k + 1:02d}T00:00:00+00:00", "world": world, "name": f"n{k}", "contact": "c",
             "side": s, "why": ""} for k, s in enumerate(sides)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return rows


def test_requests_pages_newest_first_and_offset_reaches_the_rest(tmp_path):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    _write_requests(tmp_path / "seat-requests.jsonl", w.id, ["hold", "keth", "hold", "any", "keth"])
    eng.requests_path = tmp_path / "seat-requests.jsonl"
    everything = gm.requests(limit=500)
    assert [r["name"] for r in everything] == ["n4", "n3", "n2", "n1", "n0"]  # newest first, as before
    assert [r["name"] for r in gm.requests(limit=2, offset=0)] == ["n4", "n3"]
    assert [r["name"] for r in gm.requests(limit=2, offset=2)] == ["n2", "n1"]
    assert [r["name"] for r in gm.requests(limit=2, offset=4)] == ["n0"]
    assert gm.requests(limit=2, offset=5) == []


def test_requests_side_filter_applies_before_the_page(tmp_path):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    _write_requests(tmp_path / "seat-requests.jsonl", w.id, ["hold", "keth", "hold", "any", "keth"])
    eng.requests_path = tmp_path / "seat-requests.jsonl"
    assert [r["name"] for r in gm.requests(side="hold")] == ["n2", "n0"]
    assert [r["name"] for r in gm.requests(side="keth", limit=1, offset=1)] == ["n1"]


def test_requests_refuses_a_bad_page_with_the_range(tmp_path):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    eng.requests_path = tmp_path / "none.jsonl"
    with pytest.raises(Rejected):
        gm.requests(limit=0)
    with pytest.raises(Rejected):
        gm.requests(limit=501)
    with pytest.raises(Rejected):
        gm.requests(offset=-1)
