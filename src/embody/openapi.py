"""The door's API as OpenAPI 3.1 (GET /openapi.json) and a page to read and try it (GET /docs). Every op is one
POST /op/<name>, described from the MCP tool of the same name (its doc and its argument schema), so the two doors
never drift apart. Neither path needs a grant: they describe the engine, not a world."""

from __future__ import annotations

import copy
import inspect
from typing import Any

from . import __version__
from .grants import allowed

# the most open role first: an op is filed under the first role that may call it
ORDER = ("observer", "player", "mind", "narrator", "builder", "author", "owner", "oracle")
# a tool argument the door names as the op does (the tool's own `principal` is the MCP door's sub-principal)
_RENAMED = {"invite": {"as_principal": "principal"}}
_WAIT_MAX = 120

_REFUSAL = {
    "type": "object",
    "description": "A refusal, in the same shape on every door: what went wrong and the next call to make.",
    "properties": {
        "ok": {"type": "boolean", "const": False},
        "reason": {"type": "string", "description": "why the op was refused"},
        "hint": {"type": "string", "description": "what to do next"},
        "alternatives": {"type": "array", "items": {"type": "string"}, "description": "names that would work"},
    },
    "required": ["ok", "reason"],
}

_ABOUT = """embody is a deterministic world engine for agents. This is its plain HTTPS door: every op is a
`POST /op/<name>` with a JSON object of its arguments and `Authorization: Bearer <token>`, the token from an invite
link. The same ops are MCP tools at `/mcp`, with the same role check and the same refusals.

- **Layers.** Ops are grouped by what they touch: in the world (your character), your seat, to the owner (outside
  the story, to the people who keep the world), keeping the world, building, oracle.
- **Roles.** A grant has one role, and each op names the roles that may call it. `GET /op` lists the ops your grant
  may call. `/openapi.json?role=player` (or mind, observer, narrator, builder, author, owner, oracle) shows one role's ops.
- **Refusals** come back as 200 with `{"ok": false, "reason", "hint"}`. The hint is the next call to make.
- **wait** is capped at 120 seconds over this door: call it again to keep listening.
- **Names, not ids.** Ops take a name wherever they take an entity, and refuse when one is ambiguous."""


def _takes(op: str) -> set[str] | None:
    """The arguments the door passes to this op (the Session method's own), or None when it takes any (**kw)."""
    from .ops import Session
    ps = inspect.signature(getattr(Session, op)).parameters
    if any(p.kind == p.VAR_KEYWORD for p in ps.values()):
        return None
    return set(ps) - {"self"}


def _body(op: str, schema: dict[str, Any]) -> dict[str, Any]:
    """A tool's argument schema as the door takes it: renamed where the door names it as the op does, without the
    tool-only arguments, without pydantic's titles."""
    s = copy.deepcopy(schema or {"type": "object"})
    props = s.setdefault("properties", {})
    req = list(s.get("required") or [])
    for a, b in _RENAMED.get(op, {}).items():
        if a in props:
            props[b] = props.pop(a)
            req = [b if r == a else r for r in req]
    keep = _takes(op)
    if keep is not None:
        for k in [k for k in props if k not in keep]:
            props.pop(k)
    for p in props.values():
        p.pop("title", None)
    if op == "wait" and "timeout" in props:
        props["timeout"]["maximum"] = _WAIT_MAX
        props["timeout"]["description"] = f"seconds to wait, at most {_WAIT_MAX} over this door"
    s.pop("title", None)
    req = [r for r in req if r in props]
    if req:
        s["required"] = req
    else:
        s.pop("required", None)
    return s


def _summary(doc: str) -> str:
    first = doc.split("\n\n")[0].replace("\n", " ").strip()
    cut = first.find(". ")
    return (first[:cut + 1] if 0 < cut < 140 else first[:140]).strip()


def roles_for(op: str) -> list[str]:
    return [r for r in ORDER if allowed(r, op)]


def spec(tools: list[dict[str, Any]], origin: str | None = None, role: str | None = None) -> dict[str, Any]:
    """The OpenAPI document. tools: [{name, description, input_schema}] (the MCP server's list); origin: the server's
    own URL as the client sees it; role: only that role's ops."""
    from .ops import LAYERS, LAYER_OF, OPS
    by_name = {t["name"]: t for t in tools}
    paths: dict[str, Any] = {}
    used: list[str] = []
    for op in OPS:
        t = by_name.get(op)
        roles = roles_for(op)
        if t is None or not roles or (role and role not in roles):
            continue
        doc = inspect.cleandoc(t.get("description") or "")
        tag = LAYER_OF.get(op, "door")
        if tag not in used:
            used.append(tag)
        paths[f"/op/{op}"] = {"post": {
            "operationId": op,
            "summary": _summary(doc) or op,
            "description": doc + f"\n\n**Layer:** {tag}. **Roles:** " + ", ".join(roles) + ".",
            "x-layer": tag,
            "tags": [tag],
            "x-roles": roles,
            "requestBody": {"required": True, "content": {"application/json": {"schema": _body(op, t.get("input_schema"))}}},
            "responses": {
                "200": {"description": "The op's result, or a refusal in the same shape on every door",
                        "content": {"application/json": {"schema": {"oneOf": [
                            {"type": "object", "description": "the op's result"},
                            {"type": "array", "description": "the op's result"},
                            {"$ref": "#/components/schemas/Refusal"}]}}}},
                "400": {"$ref": "#/components/responses/BadBody"},
                "401": {"$ref": "#/components/responses/NoGrant"},
            },
        }}
    paths["/op"] = {"get": {
        "operationId": "list_ops", "summary": "The ops this grant may call", "tags": ["door"],
        "responses": {"200": {"description": "{ops, role, how}", "content": {"application/json": {"schema": {
            "type": "object", "properties": {"ops": {"type": "array", "items": {"type": "string"}},
                                             "layers": {"type": "object", "description": "the same ops by layer"},
                                             "role": {"type": "string"}, "how": {"type": "string"}}}}}},
                      "401": {"$ref": "#/components/responses/NoGrant"}}}}
    paths["/op/principals"] = {"post": {
        "operationId": "principals", "summary": "Who this grant speaks for: its own principal and any sub-principals",
        "tags": ["door"], "requestBody": {"required": False, "content": {"application/json": {"schema": {"type": "object"}}}},
        "responses": {"200": {"description": "[{id, role, entity, main}, ...]", "content": {"application/json": {
            "schema": {"type": "array", "items": {"type": "object"}}}}},
                      "401": {"$ref": "#/components/responses/NoGrant"}}}}
    paths["/health"] = {"get": {
        "operationId": "health", "summary": "Whether the server is up (no grant, no world data)", "tags": ["door"],
        "security": [], "responses": {"200": {"description": '{"ok": true, "embody": "up"}'}}}}
    tags = [{"name": n, "description": d + " Each op lists every role that may call it."}
            for n, (d, _) in LAYERS.items() if n in used]
    tags.append({"name": "door", "description": "The door itself: what it serves and whether it is up."})
    out: dict[str, Any] = {
        "openapi": "3.1.0",
        "info": {"title": "embody", "version": __version__, "description": _ABOUT,
                 "license": {"name": "MIT", "identifier": "MIT"}},
        "tags": tags,
        "paths": paths,
        "security": [{"bearer": []}],
        "components": {
            "securitySchemes": {"bearer": {"type": "http", "scheme": "bearer",
                                           "description": "The token from your invite link's page"}},
            "schemas": {"Refusal": _REFUSAL},
            "responses": {
                "BadBody": {"description": "The body is not a JSON object",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Refusal"}}}},
                "NoGrant": {"description": "No valid grant on this request: send the bearer token from your invite",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Refusal"}}}},
            },
        },
    }
    if origin:
        out["servers"] = [{"url": origin}]
    if role:
        out["info"]["title"] = f"embody ({role})"
    return out


# Swagger UI from a pinned CDN build. It keeps no token between visits (persistAuthorization off): a grant typed into
# Authorize lives in this tab only.
DOCS_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>embody API</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css">
<style>body { margin: 0; background: #fafafa; } .swagger-ui .topbar { display: none; }</style>
</head>
<body>
<div id="ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
<script>
const role = new URLSearchParams(location.search).get("role");
SwaggerUIBundle({
  url: "openapi.json" + (role ? "?role=" + encodeURIComponent(role) : ""),
  dom_id: "#ui", deepLinking: true, docExpansion: "none", filter: true, persistAuthorization: false,
  defaultModelsExpandDepth: 0,
});
</script>
</body>
</html>
"""
