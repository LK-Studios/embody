"""Paging for the catalog, roster and per-place ops: worlds, schemas, scripts, timers, seats, minds, programs, inspect
and recall. Every op keeps its default result when no window is asked for, filters apply before the page, sort names
a field the rows have, and a bad page is refused with the range."""

import pytest

from embody.ops import Rejected
from tests.test_flaws import player
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def _all_pages(fn, step=1, **kw):
    out, off = [], 0
    while True:
        page = fn(limit=step, offset=off, **kw)
        if not page:
            return out
        out += page
        off += step


def test_schemas_pages_cover_every_kind_once_and_filter_by_extends():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    full = gm.schemas()
    assert len(full) >= 3
    assert [s["id"] for s in _all_pages(gm.schemas, step=2)] == [s["id"] for s in full]
    assert all(s["extends"] == "thing" for s in gm.schemas(extends="thing"))
    assert [s["id"] for s in gm.schemas(sort="-id")] == sorted((s["id"] for s in full), reverse=True)
    with pytest.raises(Rejected) as r:
        gm.schemas(sort="nope")
    assert "sort by a field" in r.value.hint
    with pytest.raises(Rejected):
        gm.schemas(limit=0)


def test_scripts_name_filter_and_paging():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    full = gm.scripts()
    assert all(s["id"] in {x["id"] for x in full} for s in gm.scripts(name=full[0]["id"][:3]) if full)
    assert [s["id"] for s in _all_pages(gm.scripts, step=1)] == [s["id"] for s in full]


def test_worlds_pages_and_sorts_the_server_list():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    full = gm.worlds()
    assert len(full) >= 1
    assert gm.worlds(limit=1, offset=len(full)) == []
    assert gm.worlds(sort="name")[0]["name"] <= gm.worlds(sort="-name")[0]["name"]


def test_seats_held_filter_and_page():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    everything = gm.seats()["seats"]
    assert gm.seats(held=True)["seats"] == [] or all(s["embodied_by"] for s in gm.seats(held=True)["seats"])
    assert all(not s["embodied_by"] for s in gm.seats(held=False)["seats"])
    assert len(gm.seats(limit=1)["seats"]) <= 1
    assert len(gm.seats(offset=len(everything))["seats"]) == 0
    assert "templates" in gm.seats()  # templates and hints stay whole


def test_minds_rows_page_and_filter_but_alerts_stay_whole():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    full = gm.minds()
    assert len(gm.minds(limit=1)["minds"]) <= 1
    assert gm.minds(seated=True)["minds"] == [m for m in full["minds"] if m["seated"]]
    assert gm.minds(offset=10**6)["minds"] == []
    assert gm.minds()["alerts"] == full["alerts"]


def test_timers_page():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    full = gm.timers()
    assert gm.timers(limit=1)[: 1] == full[:1]
    assert gm.timers(offset=len(full) + 1) == []


def test_inspect_pages_contents_and_relations():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    whole = gm.inspect("Hall")
    assert len(whole["contents"]) >= 1
    assert gm.inspect("Hall", limit=1)["contents"] == whole["contents"][:1]
    assert gm.inspect("Hall", limit=1, offset=len(whole["contents"]))["contents"] == []
    assert gm.inspect("Hall", limit=1)["name"] == "Hall"  # the card itself is not paged
    with pytest.raises(Rejected):
        gm.inspect("Hall", limit=0)


def test_recall_pages_edges_and_refuses_a_bad_offset():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    sam, _ = player(eng, gm)
    assert len(sam.recall(limit=1)["edges"]) <= 1
    assert sam.recall(limit=1, offset=10**6)["edges"] == []
    with pytest.raises(Rejected):
        sam.recall(offset=-1)


def test_programs_pages_when_there_are_verbs_or_frames():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    out = gm.programs(limit=1)
    assert isinstance(out, dict)
    key = "verbs" if "verbs" in out else "frames" if "frames" in out else None
    if key:
        assert len(out[key]) <= 1
