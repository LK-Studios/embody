"""A read-only grant on one part of the world (an observer with limits.under): a game's client reads that part as
anyone standing there sees it, nothing hidden, no one's notes, and writes nothing."""

import pytest

from embody.world import Rejected
from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def reader(eng):
    gm = owner(eng)
    vault = gm.spawn("place", "Hall", "Vault", state={"hidden": True})["id"]
    gm.spawn("thing", vault, "Ledger of Debts")
    gm.patch("Guard", {"brief": "You guard the vault and say nothing of it.", "secret": ["post"], "post": "the vault"})
    gm.remember("the vault code is the guard's birthday", entity="Guard")
    gm.layout(frame={"units": "m"}, placements=[{"entity": "Cell", "at": [0, 0, 0], "radius": 4},
                                                {"entity": "Hall", "at": [20, 0, 0], "size": [12, 8]},
                                                {"entity": vault, "at": [24, 0, -3], "radius": 1},
                                                {"entity": "Guard", "at": [18, 0, 0]}])
    inv = gm.invite("observer", label="ridge kid", limits={"under": "Hall"})
    s = eng.session_for_token(inv["token"])
    s.use("two-rooms")
    return gm, s, vault, inv


def test_a_read_only_grant_maps_its_part_and_reads_it_as_anyone_would():
    eng, w, i = engine_with_two_rooms()
    gm, s, vault, inv = reader(eng)
    assert "reads only under Hall" in inv["page"]
    names = {e["name"] for e in s.map()["entities"]}
    assert "Guard" in names and "Vault" not in names and "Ledger of Debts" not in names
    for ref in ("Vault", vault, "Ledger of Debts", "Cell", "Prisoner"):
        with pytest.raises(Rejected, match="nothing called"):
            s.inspect(ref)
    st = s.inspect("Guard")["state"]
    assert not {"brief", "memory", "post", "goals"} & set(st)
    assert [c["name"] for c in s.find(type="creature")] == ["Guard"]
    assert s.find(state={"post": "the vault"}) == []  # no oracle on a secret key
    b = s.perceive(from_entity="Hall")
    assert b["here"]["name"] == "Hall" and "Vault" not in {c["name"] for c in b["present"]}
    assert "events" not in b and "you" not in b
    assert s.looks("Guard")["name"] == "Guard"
    assert s.measure("Guard", "Hall")["b"]["name"] == "Hall"


def test_a_read_only_grant_writes_nothing_and_reads_no_ones_feed():
    eng, w, i = engine_with_two_rooms()
    gm, s, vault, inv = reader(eng)
    for op, kw in [("patch", {"entity": "Guard", "changes": {"hp": 0}}), ("spawn", {"type": "thing", "parent": "Hall"}),
                   ("history", {}), ("recall", {"entity": "Guard"}), ("say", {"text": "hello"}), ("timers", {}),
                   ("summary", {}), ("verify", {}), ("wait", {"timeout": 0}), ("join", {"entity": "Guard"}),
                   ("scripts", {}), ("act", {"verb": "go"})]:
        with pytest.raises(Rejected, match="not open to a read-only grant"):
            getattr(s, op)(**kw)
    assert s._reader() and not s._privileged()  # the hosted viewer refuses it on the same test
    with pytest.raises(Rejected, match="under=<entity> alone"):
        gm.invite("observer", limits={"under": "Hall", "types": ["thing"]})
    whole = eng.session_for_token(gm.invite("observer", label="the whole")["token"])
    whole.use("two-rooms")
    assert "Vault" in {e["name"] for e in whole.map(under="Hall")["entities"]}  # an observer with no limits reads all


def test_a_read_only_grant_is_shown_only_what_it_may_call(tmp_path):
    import asyncio
    import json
    from embody.mcp_server import _current, build_server, http_app
    from embody.ops import OPS, _READER_OPS, call
    eng, w, i = engine_with_two_rooms()
    gm, s, vault, inv = reader(eng)
    shown = {op for op in OPS if s.may(op)}
    assert shown == {op for op in _READER_OPS if op in OPS} and "script_source" not in shown and "wait" not in shown
    for op in set(OPS) - shown:  # and every op it is not shown is refused when called
        assert "read-only grant" in call(s, op)["reason"], op
    srv = build_server(gm, tmp_path / "x.db", eng, http_only=True)
    tok = _current.set(s)
    try:
        tools = {t.name for t in asyncio.run(srv.list_tools())}
    finally:
        _current.reset(tok)
    assert tools - {"principals"} == shown
    out = {}

    async def get():
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(msg):
            out.setdefault("body", b"")
            out["body"] += msg.get("body", b"")
        await http_app(srv)({"type": "http", "method": "GET", "path": "/op", "query_string": b"", "scheme": "http",
                             "headers": [(b"authorization", f"Bearer {inv['token']}".encode())]}, receive, send)
    asyncio.run(get())
    assert set(json.loads(out["body"])["ops"]) == shown
