"""Paged asks: newest first, status and kind filters before the page, and listing a page marks only its news read."""

import pytest

import embody.ops as ops
from embody.ops import Rejected
from tests.test_flaws import player
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def _asks(eng, gm, sam, n):
    ids = []
    for k in range(n):
        ids.append(sam.ask_owner("testing", what=f"a reviewer {k}", why="I tried the case")["id"])
    return ids


def test_asks_pages_newest_first(monkeypatch):
    monkeypatch.setattr(ops, "ASK_PER_HOUR", 50)
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    ids = _asks(eng, gm, sam, 5)
    got = [a["id"] for a in gm.asks_to_owner(limit=500)["asks"]]
    assert got == list(reversed(ids))
    assert [a["id"] for a in gm.asks_to_owner(limit=2, offset=2)["asks"]] == list(reversed(ids))[2:4]
    assert gm.asks_to_owner(limit=2, offset=5)["asks"] == []


def test_listing_a_page_marks_only_that_pages_news_read(monkeypatch):
    monkeypatch.setattr(ops, "ASK_PER_HOUR", 50)
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    ids = _asks(eng, gm, sam, 4)
    gm.answer_ask(ids[0], "answered", "thanks")  # the oldest ask gets an answer: news for sam
    sam.asks_to_owner(limit=2, offset=0)  # the newest two: no news there
    assert [r["id"] for r in eng.asks.fold(w.id) if r.get("news")] == [ids[0]]  # still news
    sam.asks_to_owner(limit=2, offset=2)  # the page that holds it
    assert [r["id"] for r in eng.asks.fold(w.id) if r.get("news")] == []


def test_status_and_kind_filter_before_the_page(monkeypatch):
    monkeypatch.setattr(ops, "ASK_PER_HOUR", 50)
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    ids = _asks(eng, gm, sam, 3)
    gm.answer_ask(ids[1], "declined", "no")
    assert [a["id"] for a in sam.asks_to_owner(status="declined")["asks"]] == [ids[1]]
    assert len(gm.asks_to_owner(kind="testing", limit=2, offset=1)["asks"]) == 2


def test_asks_refuses_a_bad_page(monkeypatch):
    monkeypatch.setattr(ops, "ASK_PER_HOUR", 50)
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    with pytest.raises(Rejected):
        gm.asks_to_owner(limit=0)
    with pytest.raises(Rejected):
        gm.asks_to_owner(limit=501)
    with pytest.raises(Rejected):
        gm.asks_to_owner(offset=-1)
