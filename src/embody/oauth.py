"""Sign-in for a connector that wants OAuth (Claude's custom connectors, on claude.ai and its apps): the door is its
own authorization server, and the invite link is the sign-in.

A guest adds their invite link as the connector's URL. Its first call has no token, so the door answers 401 and names
the protected resource's metadata; the connector reads it, registers itself, and opens /authorize in a browser, where
the guest taps Connect for the seat the link stands for. The code it gets back buys an access token and a refresh
token at /token (PKCE, S256), and every call after that carries the access token as an ordinary bearer.

Nothing new is stored. Clients, codes and tokens are sealed: a JSON payload signed with HMAC-SHA256 under a key kept
beside the database (oauth.key, made on first use), so a restart forgets nothing that matters. A token names its
grant and a digest of the grant's own token: revoking the grant ends it, and so does a relink, which gives the grant a
new token. Codes live five minutes and are spent once; access tokens a day; refresh tokens half a year."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlsplit

PREFIX = "oa."  # every sealed thing starts so; a bearer that does is an OAuth token, not a grant's own
CODE_S = 300.0
ACCESS_S = 24 * 3600.0
REFRESH_S = 180 * 24 * 3600.0


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def digest(text: str, n: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:n]


def key_for(db: Path | str | None) -> bytes:
    """The sealing key: oauth.key beside the database, made on first use; a fresh one per process for a database in
    memory (its tokens die with it anyway)."""
    if db is None or str(db) == ":memory:":
        return secrets.token_bytes(32)
    path = Path(db).with_name("oauth.key")
    try:
        text = path.read_text(encoding="ascii").strip()
        if len(text) >= 64:
            return bytes.fromhex(text[:64])
    except (OSError, ValueError):
        pass
    key = secrets.token_bytes(32)
    try:
        path.write_text(key.hex(), encoding="ascii")
    except OSError:
        pass
    return key


class Sealer:
    """Seal and open small payloads: `oa.<payload>.<signature>`, with a kind so one sort is never taken for another."""

    def __init__(self, key: bytes):
        self.key = key

    def _sig(self, body: str) -> str:
        return _b64(hmac.new(self.key, body.encode("ascii"), hashlib.sha256).digest()[:18])

    def seal(self, kind: str, payload: dict[str, Any]) -> str:
        body = _b64(json.dumps({"k": kind, **payload}, separators=(",", ":")).encode("utf-8"))
        return f"{PREFIX}{body}.{self._sig(body)}"

    def open(self, kind: str, sealed: str | None, now: float | None = None) -> dict[str, Any] | None:
        if not sealed or not sealed.startswith(PREFIX):
            return None
        body, _, sig = sealed[len(PREFIX):].rpartition(".")
        if not body or not hmac.compare_digest(sig, self._sig(body)):
            return None
        try:
            p = json.loads(_unb64(body))
        except ValueError:
            return None
        if not isinstance(p, dict) or p.get("k") != kind:
            return None
        if p.get("exp") is not None and float(p["exp"]) <= (time.time() if now is None else now):
            return None
        return p


def peek_world(sealed: str) -> str | None:
    """The world a sealed token names, unverified: for a hub to route it; the world's own server checks it."""
    try:
        return json.loads(_unb64(sealed[len(PREFIX):].rpartition(".")[0])).get("w")
    except (ValueError, AttributeError):
        return None


def pkce_ok(verifier: str, challenge: str) -> bool:
    return bool(verifier) and bool(challenge) and hmac.compare_digest(
        _b64(hashlib.sha256(verifier.encode("ascii", "ignore")).digest()), challenge)


def invite_code(text: str | None) -> str | None:
    """The code in an invite link (.../i/<code>), or a bare code pasted on its own."""
    text = (text or "").strip()
    if not text:
        return None
    if "/i/" in text:
        text = urlsplit(text).path.split("/i/", 1)[1] if "://" in text else text.split("/i/", 1)[1]
    code = text.strip("/").split("/")[0].split("?")[0]
    return code if code and all(c.isalnum() or c in "-_" for c in code) else None


# ---- metadata ---------------------------------------------------------------------------------------------------------

def resource_metadata(origin: str, resource: str, name: str) -> dict[str, Any]:
    """RFC 9728: who signs a client in for this resource."""
    return {"resource": resource, "authorization_servers": [origin], "bearer_methods_supported": ["header"],
            "resource_name": name, "scopes_supported": ["play"]}


def server_metadata(origin: str) -> dict[str, Any]:
    """RFC 8414: where to register, sign in and buy tokens."""
    return {"issuer": origin, "authorization_endpoint": f"{origin}/authorize", "token_endpoint": f"{origin}/token",
            "registration_endpoint": f"{origin}/register", "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"], "scopes_supported": ["play"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"]}


def redirect_ok(uri: str) -> bool:
    """A redirect a client may register: https, or http to this machine (a local client)."""
    try:
        u = urlsplit(uri)
    except ValueError:
        return False
    return u.scheme == "https" and bool(u.netloc) or u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1")


def with_query(uri: str, params: dict[str, str]) -> str:
    return uri + ("&" if "?" in uri else "?") + urlencode({k: v for k, v in params.items() if v is not None})


# ---- the sign-in page -------------------------------------------------------------------------------------------------

def sign_in_page(world: str, who: str | None, fields: dict[str, str], error: str = "") -> bytes:
    """The page a guest sees when their connector signs in: one tap to connect the seat their link stands for, or a box
    for the link when the connector did not say which (it was added by the door's plain URL)."""
    e = html.escape
    hidden = "".join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k, v in fields.items() if v)
    if who is not None:
        ask = f"<p>Connect Claude to <b>{e(who)}</b> in {e(world)}?</p>"
        box = ""
    else:
        ask = f"<p>Paste the invite link you were sent for {e(world)}.</p>"
        box = ('<input name="invite" placeholder="https://.../i/..." autocomplete="off" '
               'style="width:100%;padding:12px;font-size:16px;box-sizing:border-box;margin:8px 0 16px">')
    err = f'<p style="color:#b42318">{e(error)}</p>' if error else ""
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(world)}: connect</title>
<style>body{{font-family:system-ui,sans-serif;max-width:28rem;margin:12vh auto;padding:0 16px;color:#1d1d1f;
background:#faf9f6}}@media (prefers-color-scheme:dark){{body{{color:#eee;background:#161616}}}}
button{{font-size:17px;padding:12px 22px;border-radius:10px;border:0;cursor:pointer}}
.go{{background:#1d6b4f;color:#fff}}.no{{background:transparent;color:inherit;text-decoration:underline}}</style>
</head><body><h1 style="font-size:1.4rem">{e(world)}</h1>{ask}{err}
<form method="post" action="/authorize">{hidden}{box}
<button class="go" name="decision" value="allow">Connect</button>
<button class="no" name="decision" value="deny">Cancel</button></form>
<p style="opacity:.7;font-size:.9rem">This lets your Claude play your seat: it can act and speak as your character,
nothing else. The host can end it at any time.</p></body></html>"""
    return page.encode("utf-8")
