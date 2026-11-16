"""Looks: a body's appearance as data beside its description (Nate 2026-11-16).

The description is the base look, set once. Beside it a body carries `looks`: {regions, marks, next}. `regions` is the
body plan (the human twelve when it names none); a mark of kind grown or replaced may name a region the plan lacks (a
tail, horns), and that adds it. A mark is {where, what, kind, band, since, by, lasts}:

- kind: worn-on (paint, dye: gone after `lasts` world days), permanent (a tattoo, a scar, a brand), replaced (the
  region's base look is swapped: its line is the mark's, not the base plus it) or grown (age, a beard).
- band: how near one must be to see it: far (seen from afar too), near (anyone in the same place), close (within
  CLOSE_M metres, or the body itself).

A grown mark may carry `stages`, [{after_days, what, band?}] in order: on read its line is the last stage passed since
`since` (before the first, its own `what`), worked out from the clock like a fade, so hair grows with no tick. An empty
`what` shows no line (clean-shaven). A cut (ctx.regrow) moves `since` back to a stage. A body plan may carry `growth`
{region: stages}: a body made from that template starts with those marks at its join.

A thing the body holds with `covers: [regions]` hides marks on those regions, unless it says `worn: false`. Only the
world's rules write looks (ctx.mark, ctx.unmark, or the owner's patch): `looks` is one of the body's rules-only keys.
"""

from __future__ import annotations

from typing import Any

REGIONS = ["head", "face", "eyes", "hair", "neck", "torso", "back", "arms", "hands", "legs", "feet", "skin"]
KINDS = ("worn-on", "permanent", "replaced", "grown")
BANDS = ("close", "near", "far")  # nearest first: a viewer at a band sees marks of that band and every farther one
CLOSE_M = 2.0
MAX_WHAT = 200
MAX_WHERE = 40
MAX_MARKS = 40
MAX_STAGES = 12


def of(state: dict[str, Any]) -> dict[str, Any]:
    v = state.get("looks")
    return v if isinstance(v, dict) else {}


def fades_at(m: dict[str, Any], day: float) -> float | None:
    if m.get("kind") != "worn-on" or m.get("lasts") is None:
        return None
    return float(m.get("since") or 0) + float(m["lasts"]) * day


def live(lk: dict[str, Any], t: float, day: float) -> dict[str, dict[str, Any]]:
    """The marks still on the body: a worn-on mark past its `lasts` is gone."""
    out = {}
    for mid, m in (lk.get("marks") or {}).items():
        if not isinstance(m, dict):
            continue
        f = fades_at(m, day)
        if f is None or t < f:
            out[mid] = m
    return out


def faded(lk: dict[str, Any], t: float, day: float) -> list[str]:
    marks = lk.get("marks") or {}
    return [mid for mid in marks if isinstance(marks[mid], dict) and mid not in live(lk, t, day)]


def stage(m: dict[str, Any], t: float, day: float) -> tuple[dict[str, Any], int | None, float | None]:
    """A grown mark as it reads now: (the mark with the passed stage's what and band, the stage's index or None before
    the first, when the next stage starts or None). Any other mark reads as it is."""
    st = m.get("stages")
    if m.get("kind") != "grown" or not isinstance(st, list) or not st:
        return m, None, None
    since = float(m.get("since") or 0)
    gone = (t - since) / day
    i = max((k for k, s in enumerate(st) if float(s.get("after_days") or 0) <= gone), default=None)
    nxt = 0 if i is None else i + 1
    at = since + float(st[nxt].get("after_days") or 0) * day if nxt < len(st) else None
    if i is None:
        return m, None, at
    return {**m, "what": st[i].get("what") or "", "band": st[i].get("band") or m.get("band") or "near"}, i, at


def seed(lk: dict[str, Any], t: float, by: str | None) -> dict[str, Any]:
    """The marks a body plan's `growth` {region: stages} starts a new body with, grown from `t`: a looks patch."""
    growth = lk.get("growth")
    if not isinstance(growth, dict) or not growth:
        return {}
    n = int(lk.get("next") or 1)
    marks = {}
    for region, st in list(growth.items())[:MAX_MARKS]:
        if not isinstance(st, list) or not st:
            continue
        marks[f"m{n}"] = {"where": str(region).lower(), "what": "", "kind": "grown", "band": "near", "since": t,
                          "by": by, "stages": [dict(s) for s in st[:MAX_STAGES] if isinstance(s, dict)]}
        n += 1
    return {"marks": marks, "next": n} if marks else {}


def regions(lk: dict[str, Any], marks: dict[str, dict[str, Any]] | None = None) -> list[str]:
    """The body plan, and any region a grown or replaced mark added."""
    out = list(lk.get("regions") or REGIONS)
    for m in (marks if marks is not None else lk.get("marks") or {}).values():
        if isinstance(m, dict) and m.get("kind") in ("grown", "replaced") and m.get("where") not in out:
            out.append(m["where"])
    return out


def covered(world: Any, body_id: str) -> set[str]:
    """The regions what the body holds covers: a held thing with `covers`, unless it says `worn: false`."""
    out: set[str] = set()
    for c in world.children(body_id):
        cov = c["state"].get("covers")
        if cov and c["state"].get("worn") is not False:
            out.update(str(r) for r in (cov if isinstance(cov, list) else [cov]))
    return out


def sees(viewer_band: str, mark_band: str) -> bool:
    """Whether a viewer at a band sees a mark of a band ("self" sees everything)."""
    if viewer_band == "self":
        return True
    b = mark_band if mark_band in BANDS else "near"
    return BANDS.index(b) >= BANDS.index(viewer_band)


def order(x: tuple[str, dict[str, Any]]) -> tuple[float, int, str]:
    """Marks in the order they were made: by world time, then by their number (m1, m2...) within one second."""
    mid, m = x
    n = int(mid[1:]) if mid[1:].isdigit() else 0
    return float(m.get("since") or 0), n, mid


def lines(regs: list[str], marks: list[tuple[str, dict[str, Any]]], note_covered: bool = False,
          cover: set[str] | None = None) -> list[str]:
    """A line a region, in the plan's order: "Arms: a ring of Keth knots inked round the left forearm." A replaced
    mark takes the region's line (the latest when there are several); the others join it with "; "."""
    by: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for mid, m in marks:
        by.setdefault(m.get("where"), []).append((mid, m))
    out = []
    for r in regs:
        ms = sorted(by.get(r, []), key=order)
        if not ms:
            continue
        last = max((i for i, x in enumerate(ms) if x[1].get("kind") == "replaced"), default=None)
        if last is not None:
            ms = ms[last:]  # the part as it is now, and what was done to it since
        text = "; ".join(str(m.get("what")) for _, m in ms)
        tail = " (covered)" if note_covered and cover and r in cover else ""
        out.append(f"{r[:1].upper()}{r[1:]}: {text.rstrip('.')}.{tail}")
    return out


def view(world: Any, e: dict[str, Any], viewer_band: str, t: float, day: float, full: bool) -> dict[str, Any]:
    """The looks of a body for a reader: its base description, its regions, the marks with `covered`, `seen` and
    `fades_at`, and the lines a region. `full` (the body itself, the owner, an author) lists every mark; anyone else gets
    only the marks they see from their band, uncovered."""
    lk = of(e["state"])
    marks = live(lk, t, day)
    cover = covered(world, e["id"])
    regs = regions(lk, marks)
    rows, shown = [], []
    for mid, m0 in sorted(marks.items(), key=order):
        m, at_stage, next_at = stage(m0, t, day)
        hid = m.get("where") in cover
        seen = bool(m.get("what")) and sees(viewer_band, str(m.get("band") or "near")) and not hid
        if not full and not seen:
            continue
        row = {"id": mid, "where": m.get("where"), "what": m.get("what"), "kind": m.get("kind"),
               "band": m.get("band") or "near", "since": m.get("since"), "by": m.get("by"),
               "covered": hid, "seen": seen, "fades_at": fades_at(m, day)}
        if m0.get("stages"):
            row.update({"stage": at_stage, "stages": len(m0["stages"]), "next_stage_at": next_at})
        rows.append(row)
        if m.get("what") and (seen or full):
            shown.append((mid, m))
    return {"id": e["id"], "name": e["name"], "description": e["state"].get("description"), "regions": regs,
            "marks": rows, "lines": lines(regs, shown, note_covered=full, cover=cover)}


def card_lines(world: Any, e: dict[str, Any], viewer_band: str, t: float, day: float) -> list[str]:
    """The lines a card shows: the marks the viewer sees, uncovered (the body's own card: all, covered ones noted)."""
    v = view(world, e, viewer_band, t, day, full=viewer_band == "self")
    return v["lines"]
