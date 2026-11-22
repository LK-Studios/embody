"""The hub's calls to a world never queue forever: a reply that goes silent is cut off after the read timeout, a call
the client gave up on is cancelled and its connection freed, and a call that finds every connection busy gets a 503 at
once. The world's MCP door answers GET with 405, since it has no event stream of its own to hold open."""

import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

import embody.hub as hubmod
from embody.hub import Hub, Router
from tests.test_grants import owner
from tests.test_hub import _port
from tests.test_ops import engine_with_two_rooms


def _stuck(seen: list[str]):
    """A world's server that never finishes: /half sends the start of a reply, anything else sends nothing. Each
    call notes when its caller hung up."""
    async def app(scope, receive, send):
        if scope["path"] == "/half":
            await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": b"the first part", "more_body": True})
        while (await receive())["type"] != "http.disconnect":
            pass
        seen.append(scope["path"])
    return app


def _serve(app, servers: list) -> int:
    uvicorn = pytest.importorskip("uvicorn")
    port = _port()
    s = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="critical", lifespan="off"))
    threading.Thread(target=s.run, daemon=True).start()
    servers.append(s)
    for _ in range(200):
        if s.started:
            break
        time.sleep(0.05)
    assert s.started
    return port


@pytest.fixture
def door(tmp_path, monkeypatch):
    monkeypatch.setattr(hubmod, "_UPSTREAM", {"connect": 2.0, "read": 3.0, "write": 2.0, "pool": 0.3})
    monkeypatch.setattr(hubmod, "_CONNECTIONS", 2)
    seen: list[str] = []
    servers: list = []
    hub = Hub(["w"], tmp_path / "data")
    hub.worlds["w"].port = _serve(_stuck(seen), servers)
    hub.worlds["w"].state = "up"
    yield f"http://127.0.0.1:{_serve(Router(hub), servers)}", seen
    for s in servers:
        s.should_exit = True


def _call(url: str) -> tuple[object, float]:
    a = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            r.read()
            out: object = r.status
    except urllib.error.HTTPError as e:
        out = (e.code, json.loads(e.read()))
    except Exception as e:
        out = type(e).__name__
    return out, time.monotonic() - a


def _until(cond, limit: float) -> bool:
    end = time.monotonic() + limit
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.05)
    return cond()


def test_a_reply_that_goes_silent_is_cut_off(door):
    base, seen = door
    out, took = _call(base + "/half")
    assert out != 200 and took < 8  # the read timeout (3 s here), not the client's 15
    assert _until(lambda: "/half" in seen, 3)  # and the world's side of the call is hung up too


def test_a_call_the_client_gave_up_on_frees_its_connection(door):
    base, seen = door
    host, port = base[len("http://"):].split(":")
    with socket.create_connection((host, int(port))) as s:
        s.sendall(b"GET /silent HTTP/1.1\r\nHost: x\r\n\r\n")
        time.sleep(0.5)
    assert _until(lambda: "/silent" in seen, 1.5)  # well before the read timeout would have cut it


def test_a_call_that_finds_every_connection_busy_gets_a_503(door):
    base, seen = door
    held = [threading.Thread(target=_call, args=(base + f"/silent{n}",)) for n in range(2)]
    for t in held:
        t.start()
    time.sleep(0.5)
    out, took = _call(base + "/one-more")
    assert out[0] == 503 and "calls open" in out[1]["reason"] and took < 2
    for t in held:
        t.join()


def test_the_mcp_door_answers_get_with_405():
    uvicorn = pytest.importorskip("uvicorn")
    from embody.mcp_server import build_server, http_app
    eng, w, i = engine_with_two_rooms()
    gm = owner(eng)
    tok = gm.invite("observer", label="o")["token"]
    servers: list = []
    port = _serve(http_app(build_server(gm, None, eng, http_only=True)), servers)
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/mcp", headers={
            "authorization": f"Bearer {tok}", "accept": "text/event-stream"})
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(req, timeout=5)
        assert e.value.code == 405 and e.value.headers["allow"] == "POST"
    finally:
        for s in servers:
            s.should_exit = True


def test_a_connector_goes_through_the_hub_as_the_plain_door(tmp_path):
    """/mcp/<token> reaches the world as /mcp with the token as its bearer, so the world's server never sees it in a
    path; a GET there is answered by the hub with 405 and never reaches the world."""
    seen: list[tuple[str, bytes | None]] = []

    async def world(scope, receive, send):
        while (await receive()).get("more_body"):
            pass
        seen.append((scope["path"], dict(scope["headers"]).get(b"authorization")))
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": b"{}"})

    servers: list = []
    hub = Hub(["w"], tmp_path / "data")
    hub.worlds["w"].port = _serve(world, servers)
    hub.worlds["w"].state = "up"
    base = f"http://127.0.0.1:{_serve(Router(hub), servers)}"
    try:
        req = urllib.request.Request(f"{base}/mcp/tok-123", data=b"{}", method="POST",
                                     headers={"content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            assert r.status == 200
        assert seen == [("/mcp", b"Bearer tok-123")]
        status, body = _call(f"{base}/mcp/tok-123")
        assert status[0] == 405 and seen == [("/mcp", b"Bearer tok-123")]
    finally:
        for s in servers:
            s.should_exit = True
