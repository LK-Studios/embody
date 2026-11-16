"""The door's API as OpenAPI (/openapi.json) and its page (/docs): one POST /op/<name> per op, from the MCP tools'
own docs and schemas, with the arguments the door actually passes, filed by the most open role that may call it."""

import asyncio
import json

from embody.grants import allowed
from embody.mcp_server import build_server, http_app
from embody.openapi import spec
from embody.ops import OPS
from tests.test_ops import engine_with_two_rooms


def tools_of(srv):
    return [{"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in asyncio.run(srv.list_tools())]


def refs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref":
                yield v
            else:
                yield from refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from refs(v)


def resolve(doc, ref):
    cur = doc
    for part in ref.lstrip("#/").split("/"):
        cur = cur[part]
    return cur


def test_every_op_is_a_post_with_the_arguments_the_door_takes(tmp_path):
    eng, w, i = engine_with_two_rooms()
    srv = build_server(eng.session("host"), tmp_path / "x.db", eng)
    doc = spec(tools_of(srv), origin="https://reach.example")
    assert doc["openapi"] == "3.1.0" and doc["servers"] == [{"url": "https://reach.example"}]
    for op in OPS:
        assert f"/op/{op}" in doc["paths"], op
    body = lambda op: doc["paths"][f"/op/{op}"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert "principal" in body("invite")["properties"] and "as_principal" not in body("invite")["properties"]
    assert "principal" not in body("say")["properties"]  # the MCP door's sub-principal is not the HTTP door's
    assert "principal" in body("evict")["properties"]  # evict's own argument stays
    assert body("wait")["properties"]["timeout"]["maximum"] == 120 and "poll" not in body("wait")["properties"]
    assert "heading" in body("step")["properties"] and body("say")["required"] == ["text"]
    assert "actions" in body("define_schema")["properties"]  # an op that takes **kw keeps the tool's arguments
    step = doc["paths"]["/op/step"]["post"]
    assert step["tags"] == ["player"] and "mind" in step["x-roles"] and "Roles:" in step["description"]
    assert doc["paths"]["/op/spawn"]["post"]["tags"] != ["player"]
    for r in refs(doc):
        assert resolve(doc, r), r
    json.dumps(doc)


def test_a_role_sees_its_own_ops(tmp_path):
    eng, w, i = engine_with_two_rooms()
    srv = build_server(eng.session("host"), tmp_path / "x.db", eng)
    doc = spec(tools_of(srv), role="mind")
    ops = {p.split("/")[-1] for p in doc["paths"] if p.startswith("/op/")}
    assert ops == {op for op in OPS if allowed("mind", op)} and "step" in ops and "invite" not in ops


def get(app, path, query=b""):
    out = {}

    async def run():
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(msg):
            if msg["type"] == "http.response.start":
                out["status"] = msg["status"]
                out["headers"] = dict(msg["headers"])
            else:
                out["body"] = out.get("body", b"") + msg.get("body", b"")
        await app({"type": "http", "method": "GET", "path": path, "query_string": query, "scheme": "https",
                   "headers": [(b"host", b"reach.example")]}, receive, send)
    asyncio.run(run())
    return out


def test_the_door_serves_the_spec_and_its_page_without_a_grant(tmp_path):
    eng, w, i = engine_with_two_rooms()
    app = http_app(build_server(eng.session("host"), tmp_path / "x.db", eng, http_only=True))
    r = get(app, "/openapi.json")
    doc = json.loads(r["body"])
    assert r["status"] == 200 and "/op/perceive" in doc["paths"] and doc["servers"] == [{"url": "https://reach.example"}]
    assert "/op/spawn" not in json.loads(get(app, "/openapi.json", b"role=observer")["body"])["paths"]
    bad = get(app, "/openapi.json", b"role=king")
    assert bad["status"] == 400 and "player" in json.loads(bad["body"])["alternatives"]
    page = get(app, "/docs")
    assert page["status"] == 200 and b"swagger-ui" in page["body"] and b"openapi.json" in page["body"]
    assert get(app, "/op")["status"] == 401  # the ops themselves still need a grant
