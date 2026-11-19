"""Paged lists: grants takes limit, offset, role and active filters, and a bad page is refused, never clipped."""

import pytest

from embody.ops import OPS, Rejected
from embody.openapi import _takes
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def _grants_world(n_observers: int = 5):
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    for k in range(n_observers):
        gm.invite("observer", label=f"watch {k}")
    return gm


def test_grants_without_paging_returns_every_grant_as_before():
    gm = _grants_world(5)
    rows = gm.grants()
    assert len(rows) == 5  # the five invites; the test session holds its own role without a grant row
    assert [g["created"] for g in rows] == sorted(g["created"] for g in rows)  # still oldest first


def test_grants_limit_and_offset_pages_through_all_rows_once():
    gm = _grants_world(5)
    everything = gm.grants()
    seen, off = [], 0
    while True:
        page = gm.grants(limit=2, offset=off)
        if not page:
            break
        assert len(page) <= 2
        seen += [g["id"] for g in page]
        off += 2
    assert seen == [g["id"] for g in everything]


def test_grants_role_and_active_filters_apply_before_the_page():
    gm = _grants_world(5)
    observers = gm.grants(role="observer")
    assert len(observers) == 5 and all(g["role"] == "observer" for g in observers)
    page = gm.grants(role="observer", limit=2, offset=3)
    assert [g["id"] for g in page] == [g["id"] for g in observers[3:5]]
    assert all(g["active"] for g in gm.grants(active=True))
    assert gm.grants(active=False) == []  # nothing revoked in this world


def test_grants_refuses_a_bad_page_with_the_range():
    gm = _grants_world(1)
    with pytest.raises(Rejected) as r:
        gm.grants(limit=0)
    assert "1 to 500" in str(r.value)
    with pytest.raises(Rejected):
        gm.grants(limit=501)
    with pytest.raises(Rejected):
        gm.grants(offset=-1)


def test_grants_paging_shows_up_in_the_door_schema():
    takes = _takes("grants")
    assert takes is not None and {"limit", "offset", "role", "active"} <= takes
    assert "grants" in OPS
