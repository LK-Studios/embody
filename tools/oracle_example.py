"""An example oracle (docs/ORACLES.md): the connection of one thing in a world, answering two verbs from outside it.
`search` looks a word up on Wikipedia; `fetch` reads one public web page. Standard library only.

    python tools/oracle_example.py https://your.host <file holding the oracle grant's token> [minutes]

It offers its verbs, then loops: wait() brings the calls on its thing, it does the work here, answer() sends the text
back. The world's owner reviews the verbs once (review(thing, verb)) unless the invite approved them ahead."""
import html
import ipaddress
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "embody-oracle-example/0.1"
MAX_PAGE = 300_000
MAX_TEXT = 1500
VERBS = [{"verb": "search", "doc": "Search the outside web (an encyclopedia)", "params": {"q": "what to look up"}},
         {"verb": "fetch", "doc": "Read one public web page", "params": {"url": "https://..."}, "timeout": 45}]


class Door:
    """The world's HTTPS door: POST /op/<name> with the grant's bearer token."""

    def __init__(self, base: str, token: str):
        self.base, self.token = base.rstrip("/"), token

    def op(self, name: str, **args):
        req = urllib.request.Request(f"{self.base}/op/{name}", data=json.dumps(args).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {self.token}", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"ok": False, "status": e.code, **json.loads(e.read() or b"{}")}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read(MAX_PAGE)


def search(q: str):
    hits = json.loads(get("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "opensearch", "search": q, "limit": 3, "format": "json"})))
    titles = hits[1]
    if not titles:
        return True, f"Nothing found for {q!r}."
    page = json.loads(get("https://en.wikipedia.org/api/rest_v1/page/summary/"
                          + urllib.parse.quote(titles[0].replace(" ", "_"))))
    also = "; ".join(titles[1:])
    return True, f"{titles[0]}: {page.get('extract', '')[:1200]}" + (f"\nAlso: {also}" if also else "")


def public(host: str):
    """Every address the name resolves to is on the public web: a caller may not point the oracle at the machine it
    runs on or the network behind it."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False, "that address does not resolve"
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            return False, f"{host} is not on the public web"
    return True, ""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def fetch(url: str):
    opener = urllib.request.build_opener(NoRedirect)
    for _ in range(4):  # redirects by hand, each hop checked again
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            return False, "only http and https pages"
        ok, why = public(u.hostname)
        if not ok:
            return False, why
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,text/plain"})
        try:
            with opener.open(req, timeout=10) as r:
                kind = r.headers.get("content-type", "")
                if not kind.startswith(("text/html", "text/plain")):
                    return False, f"not a text page ({kind or 'no type'})"
                body = r.read(MAX_PAGE).decode("utf-8", "replace")
                break
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("location"):
                url = urllib.parse.urljoin(url, e.headers["location"])
                continue
            return False, f"the page answered {e.code}"
    else:
        return False, "too many redirects"
    title = re.search(r"<title[^>]*>(.*?)</title>", body, re.S | re.I)
    text = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))).strip()
    return True, (html.unescape(title.group(1).strip()) if title else url) + "\n" + text[:MAX_TEXT]


WORK = {"search": lambda a: search(str(a.get("q", ""))), "fetch": lambda a: fetch(str(a.get("url", "")))}


def main() -> None:
    base, tokfile = sys.argv[1], sys.argv[2]
    end = time.time() + 60 * float(sys.argv[3]) if len(sys.argv) > 3 else float("inf")
    door = Door(base, open(tokfile).read().strip())
    print("offered:", door.op("offer", verbs=VERBS), flush=True)
    cursor = None
    while time.time() < end:
        r = door.op("wait", timeout=30, **({"since": cursor} if cursor is not None else {}))
        if r.get("ok") is False:
            print("door closed:", r.get("status"), r.get("reason"), flush=True)
            return
        cursor = r.get("cursor", cursor)
        for c in r.get("calls", []):
            t0 = time.time()
            try:
                ok, text = WORK[c["verb"]](c["args"])
            except Exception as ex:  # the work failed out here: the caller hears so, the world goes on
                ok, text = False, f"the connection failed ({type(ex).__name__})"
            res = door.op("answer", request=c["request"], text=text[:1900], ok=ok)
            print(f"call {c['request']} {c['verb']} from {c['caller']}: ok={ok}, {len(text)} chars in "
                  f"{time.time() - t0:.1f}s, {'sent' if res.get('ok') else res.get('reason')}", flush=True)


if __name__ == "__main__":
    main()
