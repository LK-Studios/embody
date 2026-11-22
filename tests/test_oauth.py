"""Sign-in for Claude's connectors (embody.oauth): the invite link is the connector's URL, its first call is told to
sign in, the connector registers itself, the guest taps Connect, and the code buys tokens that play the seat. A relink
or a revoke ends them; nothing the sign-in carries reaches the access log."""

import base64
import hashlib
import json
import logging
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

import pytest

from tests.test_grants import _free_port, owner
from tests.test_ops import engine_with_two_rooms

REDIRECT = "https://claude.ai/api/mcp/auth_callback"


class _Stay(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # a 302 is the answer, not somewhere to go
        return None


def _call(url, data=None, headers=None, method=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.build_opener(_Stay).open(req, timeout=10) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read()
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()


def _mcp(url, method, params=None, token=None):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}).encode()
    headers = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    status, h, raw = _call(url, body, headers, "POST")
    return status, h, (json.loads(raw) if raw.strip().startswith(b"{") else {})


def _form(url, fields, headers=None):
    return _call(url, urllib.parse.urlencode(fields).encode(),
                 {"content-type": "application/x-www-form-urlencoded", **(headers or {})}, "POST")


def _pkce():
    verifier = secrets.token_urlsafe(48)
    return verifier, base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()


@pytest.fixture
def door():
    uvicorn = pytest.importorskip("uvicorn")
    from embody.mcp_server import build_server, http_app
    eng, w, i = engine_with_two_rooms()
    port = _free_port()
    eng.public_url = f"http://127.0.0.1:{port}/mcp"
    gm = owner(eng)
    gm.patch("Prisoner", {"playable": True})
    lines: list[str] = []

    class Keep(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(record.getMessage())

    keep = Keep()
    config = uvicorn.Config(http_app(build_server(gm, None, eng, http_only=True)), host="127.0.0.1", port=port,
                            log_level="info")
    logging.getLogger("uvicorn.access").addHandler(keep)
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    yield eng, w, i, gm, f"http://127.0.0.1:{port}", lines
    server.should_exit = True
    t.join(timeout=5)
    logging.getLogger("uvicorn.access").removeHandler(keep)


def _register(base):
    status, _, raw = _call(f"{base}/register", json.dumps({"redirect_uris": [REDIRECT], "client_name": "Claude",
                                                           "token_endpoint_auth_method": "none"}).encode(),
                           {"content-type": "application/json"}, "POST")
    assert status == 201, raw
    return json.loads(raw)["client_id"]


def _code(base, client, challenge, state, resource=None, invite=None):
    fields = {"response_type": "code", "client_id": client, "redirect_uri": REDIRECT, "state": state,
              "code_challenge": challenge, "code_challenge_method": "S256"}
    if resource:
        fields["resource"] = resource
    status, h, raw = _form(f"{base}/authorize", {**fields, "decision": "allow", **({"invite": invite} if invite else {})})
    assert status == 302, raw
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(h["location"]).query)
    assert h["location"].startswith(REDIRECT) and q["state"] == [state]
    return q["code"][0]


def _tokens(base, client, code, verifier):
    status, _, raw = _form(f"{base}/token", {"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT,
                                             "client_id": client, "code_verifier": verifier})
    return status, json.loads(raw)


def test_a_connector_signs_in_with_the_invite_link_and_plays_the_seat(door):
    eng, w, i, gm, base, lines = door
    inv = gm.invite("player", entity="Prisoner", label="Rupert")
    link = inv["link"]
    code_in_link = link.rsplit("/", 1)[1]
    assert "press Connect and tap Connect on the page that opens" in inv["paste"]

    status, h, _ = _mcp(link, "tools/list")  # the connector's first call: no token, so sign in
    meta_url = f"{base}/.well-known/oauth-protected-resource/i/{code_in_link}"
    assert status == 401 and f'resource_metadata="{meta_url}"' in h["www-authenticate"]
    meta = json.loads(_call(meta_url)[2])
    assert meta["resource"] == link and meta["authorization_servers"] == [base] and meta["resource_name"] == "Two Rooms"
    server = json.loads(_call(f"{base}/.well-known/oauth-authorization-server")[2])
    assert server["issuer"] == base and server["registration_endpoint"] == f"{base}/register"
    assert server["code_challenge_methods_supported"] == ["S256"]

    client = _register(base)
    verifier, challenge = _pkce()
    query = urllib.parse.urlencode({"response_type": "code", "client_id": client, "redirect_uri": REDIRECT,
                                    "state": "st-123", "code_challenge": challenge, "code_challenge_method": "S256",
                                    "resource": link})
    status, h, page = _call(f"{base}/authorize?{query}")
    assert status == 200 and h["content-type"].startswith("text/html")
    assert b"Connect Claude to <b>your seat</b> in Two Rooms" in page and b'name="invite"' not in page

    code = _code(base, client, challenge, "st-123", resource=link)
    assert _tokens(base, client, code, "the-wrong-verifier")[0] == 400  # PKCE holds the code to its maker
    status, tok = _tokens(base, client, code, verifier)
    assert status == 200 and tok["token_type"] == "Bearer" and tok["access_token"].startswith("oa.")
    assert _tokens(base, client, code, verifier)[0] == 400  # a code is good once

    status, _, body = _mcp(link, "tools/list", token=tok["access_token"])
    assert status == 200 and all(t["description"].startswith("[Two Rooms: the game on this server] ")
                                 for t in body["result"]["tools"])
    status, _, body = _mcp(link, "tools/call", {"name": "join", "arguments": {}}, token=tok["access_token"])
    assert json.loads(body["result"]["content"][0]["text"])["you"]["name"] == "Prisoner"
    assert w.embodied(i["Prisoner"])["id"] == inv["principal"]
    assert _call(link)[0] == 410  # the first use spent the page, as the token's own first use does
    assert eng.session_for_token(inv["token"]) is not None  # the grant's own token still plays beside it

    status, _, raw = _form(f"{base}/token", {"grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
                                             "client_id": client})
    fresh = json.loads(raw)
    assert status == 200 and _mcp(link, "tools/list", token=fresh["access_token"])[0] == 200

    relinked = gm.relink(inv["id"])  # the host gives the seat a new link: everything signed for the old one ends
    assert _mcp(link, "tools/list", token=fresh["access_token"])[0] == 401
    status, _, raw = _form(f"{base}/token", {"grant_type": "refresh_token", "refresh_token": fresh["refresh_token"],
                                             "client_id": client})
    assert status == 400 and "relinked" in json.loads(raw)["error_description"]
    verifier, challenge = _pkce()
    status, tok = _tokens(base, client, _code(base, client, challenge, "st-456", resource=relinked["link"]), verifier)
    assert status == 200 and _mcp(relinked["link"], "tools/list", token=tok["access_token"])[0] == 200
    gm.revoke(inv["id"])
    assert _mcp(relinked["link"], "tools/list", token=tok["access_token"])[0] == 401

    secret = [code_in_link, relinked["link"].rsplit("/", 1)[1], code, "st-123", "st-456", tok["access_token"],
              fresh["access_token"], inv["token"]]
    assert not any(s in ln for ln in lines for s in secret), lines
    assert any('"POST /mcp HTTP' in ln for ln in lines) and any('"GET /authorize HTTP' in ln for ln in lines)


def test_the_plain_door_signs_in_with_a_pasted_link_and_says_no_plainly(door):
    eng, w, i, gm, base, lines = door
    inv = gm.invite("player", label="Nate")
    status, h, _ = _mcp(f"{base}/mcp", "tools/list")
    assert status == 401 and f'resource_metadata="{base}/.well-known/oauth-protected-resource"' in h["www-authenticate"]
    assert json.loads(_call(f"{base}/.well-known/oauth-protected-resource")[2])["resource"] == f"{base}/mcp"
    client = _register(base)
    verifier, challenge = _pkce()
    query = urllib.parse.urlencode({"response_type": "code", "client_id": client, "redirect_uri": REDIRECT,
                                    "state": "s", "code_challenge": challenge, "code_challenge_method": "S256"})
    page = _call(f"{base}/authorize?{query}")[2]
    assert b'name="invite"' in page and b"Paste the invite link" in page  # the door's URL names no seat: ask for it
    fields = {"response_type": "code", "client_id": client, "redirect_uri": REDIRECT, "state": "s",
              "code_challenge": challenge, "code_challenge_method": "S256", "decision": "allow"}
    status, _, page = _form(f"{base}/authorize", {**fields, "invite": f"{base}/i/not-a-real-code"})
    assert status == 200 and b"not a live invite link" in page
    status, h, _ = _form(f"{base}/authorize", {**fields, "decision": "deny"})
    assert status == 302 and "error=access_denied" in h["location"]
    status, tok = _tokens(base, client, _code(base, client, challenge, "s", invite=inv["link"]), verifier)
    assert status == 200 and _mcp(f"{base}/mcp", "tools/list", token=tok["access_token"])[0] == 200

    # a client the server does not know, or a redirect it did not register, is never redirected to
    bad = urllib.parse.urlencode({**{k: v for k, v in fields.items() if k != "decision"},
                                  "redirect_uri": "https://evil.example/cb"})
    status, h, _ = _call(f"{base}/authorize?{bad}")
    assert status == 400 and "location" not in h
    status, h, _ = _call(f"{base}/authorize?" + urllib.parse.urlencode({**{k: v for k, v in fields.items()
                                                                           if k != "decision"}, "client_id": "oa.x.y"}))
    assert status == 400
    assert _call(f"{base}/register", b'{"redirect_uris": ["ftp://x"]}', {"content-type": "application/json"},
                 "POST")[0] == 400
    assert _call(f"{base}/.well-known/openid-configuration")[0] == 404
    status, _, raw = _form(f"{base}/token", {"grant_type": "password", "username": "x"})
    assert status == 400 and json.loads(raw)["error"] == "unsupported_grant_type"


def test_the_sealer_refuses_what_it_did_not_seal(tmp_path):
    from embody.oauth import Sealer, invite_code, key_for, peek_world
    key = key_for(tmp_path / "embody.db")
    assert key == key_for(tmp_path / "embody.db") and (tmp_path / "oauth.key").exists()  # kept across restarts
    s = Sealer(key)
    tok = s.seal("access", {"g": "g1", "w": "two-rooms", "exp": time.time() + 60})
    assert s.open("access", tok)["g"] == "g1" and peek_world(tok) == "two-rooms"
    assert s.open("refresh", tok) is None  # one kind is never another
    assert Sealer(b"another key").open("access", tok) is None
    assert s.open("access", tok[:-2] + "xx") is None
    assert s.open("access", s.seal("access", {"exp": time.time() - 1})) is None  # stale
    assert invite_code("https://h.example/i/Ab_9-x") == "Ab_9-x" and invite_code("Ab_9-x") == "Ab_9-x"
    assert invite_code("https://h.example/i/Ab_9-x?y=1") == "Ab_9-x" and invite_code("not a code!") is None
