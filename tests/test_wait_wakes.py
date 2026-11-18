"""A waiting seat sleeps until an event lands, not on a timer: the store counts every event put and wakes whoever waits
on it, so a line said a moment after the wait began comes back at once, and an idle wait costs one poll a second. The
reads a poll and a perceive make stay narrow: who said what to whom, a body's moves, and the rules up its tree."""

import threading
import time

from tests.test_grants import owner
from tests.test_ops import engine_with_two_rooms


def test_a_wait_wakes_when_an_event_lands():
    eng, w, i = engine_with_two_rooms()
    owner(eng).move("Prisoner", "Hall")
    sam = eng.session("sam")
    sam.join("two-rooms", "Prisoner")
    sam.wait(timeout=0)
    got: dict = {}

    def waiting():
        a = time.monotonic()
        got["bundle"] = sam.wait(timeout=20)
        got["took"] = time.monotonic() - a

    th = threading.Thread(target=waiting)
    th.start()
    time.sleep(0.3)
    with eng.lock:
        w.say(i["Guard"], "the second bell", reach=1)
    th.join(10)
    assert [e["payload"]["text"] for e in got["bundle"]["events"] if e["kind"] == "say"] == ["the second bell"]
    assert got["took"] < 5  # woken by the line, not the timeout


def test_the_narrow_reads_match_the_whole_rows():
    eng, w, i = engine_with_two_rooms()
    w.patch(i["Hall"], {"rules": [{"script": "noop", "kinds": ["say"]}]})
    assert w.store.rules_of(w.id, i["Hall"]) == (w.get(i["Hall"])["type"], [{"script": "noop", "kinds": ["say"]}])
    assert w.store.rules_of(w.id, i["Cell"])[1] == []
    assert w.store.rules_of(w.id, "nobody") is None
    assert w.ancestors(i["Guard"]) == [w.get(i["Guard"])["parent_id"], *w.ancestors(w.get(i["Guard"])["parent_id"])]
    assert w.store.parent_of(w.id, "nobody") == (False, None)


def test_exchanges_read_both_sides_newest_last():
    eng, w, i = engine_with_two_rooms()
    owner(eng).move("Prisoner", "Hall")
    for n in range(4):
        w.say(i["Guard"], f"guard {n}", reach=1, to=i["Prisoner"]) if n % 2 == 0 else \
            w.say(i["Prisoner"], f"prisoner {n}", reach=1, to=i["Guard"])
    got = [e["payload"]["text"] for e in w.exchanges(i["Guard"], i["Prisoner"], limit=3)]
    assert got == ["prisoner 1", "guard 2", "prisoner 3"]
