"""Measure what a seat costs a world: a wait poll, a perceive, an exchange lookup, on a copy of a real database.

    uv run python tools/bench_world.py --db <world.db> --world <id> [--workspace .] [--bodies 10]

The database is copied first (SQLite's backup into a temporary folder), so the file you name is only read. The clock is
stopped on the copy, so no timer fires while it measures. Prints the median and the slowest of each read, in
milliseconds, with the world's size, so one change can be compared with the next on the same world.
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
import tempfile
import time
from pathlib import Path

from embody.ops import AUTHOR, Engine


def timed(f, n: int = 3) -> float:
    xs = []
    for _ in range(n):
        a = time.perf_counter()
        f()
        xs.append((time.perf_counter() - a) * 1000)
    return statistics.median(xs)


def line(name: str, xs: list[float]) -> str:
    return f"{name:<28} median {statistics.median(xs):8.1f} ms   slowest {max(xs):8.1f} ms" if xs else f"{name}: none"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="the world's database file (read only: a copy is measured)")
    ap.add_argument("--world", required=True, help="the world id")
    ap.add_argument("--workspace", default=".", help="the folder with worlds/ and packs/ (default: here)")
    ap.add_argument("--bodies", type=int, default=10, help="how many seated bodies to measure from (default 10)")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "bench.db"
        src = sqlite3.connect(f"file:{Path(a.db).resolve().as_posix()}?mode=ro", uri=True)
        dst = sqlite3.connect(copy)
        src.backup(dst)
        src.close()
        dst.close()
        eng = Engine(copy, workspace=Path(a.workspace), record=False)
        w = eng.world(a.world)
        gm = eng.session("bench", capabilities=[AUTHOR], world_id=w.id)
        gm.clock(run=False)
        head = w.store.next_seq(w.id) - 1
        bodies = [r["entity_id"] for r in w.store.query("principal", "world_id=? AND entity_id IS NOT NULL", (w.id,))
                  if w.get(r["entity_id"])][:a.bodies]
        print(f"{a.world}: {w.store.count('entity', 'world_id=?', (w.id,))} entities, {head} events, "
              f"{len(bodies)} seated bodies measured")
        print(line("wait poll (last 20 events)", [timed(lambda b=b: w.events(head - 20, touching=b, limit=50))
                                                  for b in bodies]))
        print(line("perceive from a body", [timed(lambda b=b: gm.perceive(from_entity=b), n=1) for b in bodies]))
        print(line("exchanges with a neighbour", [timed(lambda b=b: [w.exchanges(b, x["id"]) for x in
                                                                     w.children(w.get(b)["parent_id"] or b)[:5]])
                                                  for b in bodies]))
        eng.store.conn.close()


if __name__ == "__main__":
    main()
