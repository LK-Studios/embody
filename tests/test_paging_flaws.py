"""Paged flaws: newest first, severity filter before the page, a bad page refused with the range."""

import pytest

from embody.ops import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def _seed(eng, w):
    eng._flaws = [{"world": w.id, "what": f"hole {k}", "how": "steps", "severity": sev}
                  for k, sev in enumerate(["high", "low", "high", "medium", "low"])]


def test_flaws_pages_newest_first():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    _seed(eng, w)
    assert [r["what"] for r in gm.flaws(limit=500)] == [f"hole {k}" for k in (4, 3, 2, 1, 0)]
    assert [r["what"] for r in gm.flaws(limit=2, offset=2)] == ["hole 2", "hole 1"]
    assert gm.flaws(limit=2, offset=5) == []
    assert all(r["untrusted"] for r in gm.flaws())


def test_flaws_severity_filter_applies_before_the_page():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    _seed(eng, w)
    assert [r["what"] for r in gm.flaws(severity="high")] == ["hole 2", "hole 0"]
    assert [r["what"] for r in gm.flaws(severity="HIGH", limit=1, offset=1)] == ["hole 0"]


def test_flaws_refuses_a_bad_page():
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    with pytest.raises(Rejected):
        gm.flaws(limit=0)
    with pytest.raises(Rejected):
        gm.flaws(limit=501)
    with pytest.raises(Rejected):
        gm.flaws(offset=-1)
